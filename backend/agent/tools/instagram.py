"""Instagram evidence gathering via Apify's instagram-scraper actor.

The signal is social proof: do real accounts tag the store, and what do the
comments on its own posts say? Scam stores tend to have an Instagram page but
no organic tags from customers or creators. Tags only mean something relative
to the account's size, so each check runs three Apify jobs in parallel —
profile details (follower count), tagged posts, and the store's own posts.

The account is found by scraping the store's homepage for its Instagram link,
falling back to an Instagram search when the homepage is blocked or has none.
"""

import asyncio
import logging
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from apify_client import ApifyClientAsync

from .instagram_comments import CommentFindings, analyze_comments, parse_comments

logger = logging.getLogger(__name__)

_ACTOR_ID = "apify/instagram-scraper"
_RUN_TIMEOUT = timedelta(seconds=60)
_MAX_CHARGE_USD = Decimal("0.25")  # hard spend cap per Apify run

# The scraper returns the newest tags first, so a large brand hits this limit
# within hours; that's fine, we only need to know there are "enough".
TAG_LIMIT = 20
TAG_WINDOW_DAYS = 90
# Each post carries up to ~15 of its latest comments, so this bounds the
# comment sample at roughly 180.
POSTS_LIMIT = 12
# The search fans out to every candidate profile, so it's the slowest run (44s
# in testing); the handful of top hits is enough to find a brand's own account.
SEARCH_LIMIT = 5

# Below this the account is too small or new to judge fairly by its tags.
MIN_FOLLOWERS = 100
# A healthy store is expected to have one distinct recent tagger per this many
# followers, capped so huge brands aren't held to an absurd bar.
_FOLLOWERS_PER_EXPECTED_TAGGER = 1_000
_MAX_EXPECTED_TAGGERS = 10
# Zero tags is a warning sign, not proof of a scam, so risk never reaches 100.
_MAX_RISK = 100

_HANDLE_RE = re.compile(
    r"instagram\.com\\?/([A-Za-z0-9._]{1,30})(?![A-Za-z0-9._])", re.IGNORECASE
)
# instagram.com/<word> paths that are pages or share widgets, not profiles.
_NON_PROFILE_PATHS = {
    "p", "reel", "reels", "explore", "accounts", "stories", "tv", "share",
    "direct", "about", "developer", "legal", "sharer", "oauth", "web", "api",
    "embed", "static", "challenge", "directory", "privacy", "terms", "download",
}  # fmt: skip

# Some storefronts block non-browser user agents.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en",
}

# Second-level labels that pair with a country TLD (brand.co.uk).
_SECOND_LEVEL_LABELS = {"co", "com", "org", "net", "gov", "ac"}
# Sites a profile's website link can point to without saying anything about
# which store owns the account: link-in-bio pages, hosted storefront domains,
# and social or messaging links.
_NEUTRAL_SITES = {
    "linktr.ee", "linkin.bio", "beacons.ai", "bio.link", "lnk.bio", "campsite.bio",
    "taplink.cc", "stan.store", "allmylinks.com", "linkpop.com", "msha.ke",
    "solo.to", "carrd.co", "myshopify.com",
    "instagram.com", "facebook.com", "tiktok.com", "youtube.com", "wa.me",
    "whatsapp.com", "t.me",
}  # fmt: skip


@dataclass
class InstagramTag:
    owner: str  # the account that tagged the store
    url: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class InstagramFindings:
    handle: Optional[str] = None
    followers: Optional[int] = None
    verified: bool = False
    # Whether the profile's website links back to the store: True yes, False it
    # points elsewhere, None no evidence either way (no website, link-in-bio).
    website_match: Optional[bool] = None
    tags: list[InstagramTag] = field(default_factory=list)
    recent_taggers: int = 0  # distinct accounts that tagged within TAG_WINDOW_DAYS
    expected_taggers: Optional[int] = None
    # Why no score was produced when nothing went wrong (no link, private, tiny).
    skip_reason: Optional[str] = None
    error: Optional[str] = None  # the whole check failed (both signals)
    tags_error: Optional[str] = None  # only the tagged-posts run failed
    risk_score: Optional[int] = None  # 0-100, higher is riskier; None if unscored
    # Comments on the store's own posts, scored independently of the tags.
    comments: CommentFindings = field(default_factory=CommentFindings)


def expected_taggers(followers: int) -> int:
    """Distinct recent taggers a store of this size should have (at least 1)."""
    return round(
        min(max(followers / _FOLLOWERS_PER_EXPECTED_TAGGER, 1), _MAX_EXPECTED_TAGGERS)
    )


def count_recent_taggers(
    tags: list[InstagramTag], now: Optional[datetime] = None
) -> int:
    """Distinct accounts that tagged within the window. Tags without a
    timestamp can't be placed in the window, so they don't count."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=TAG_WINDOW_DAYS)
    return len(
        {
            tag.owner.lower()
            for tag in tags
            if tag.timestamp is not None and tag.timestamp >= cutoff
        }
    )


def tag_risk_score(followers: int, recent_taggers: int) -> int:
    """Risk 0-_MAX_RISK: how far short of the expected number of taggers the
    store falls, scaled linearly. Meeting expectations scores 0."""
    coverage = min(recent_taggers / expected_taggers(followers), 1.0)
    return round(_MAX_RISK * (1 - coverage))


def extract_handle(html: str) -> Optional[str]:
    """Most-linked Instagram profile handle in a page (footer, header, and
    JSON-LD links all count), lowercased. Ties go to the first one seen."""
    handles = [
        handle
        for match in _HANDLE_RE.finditer(html)
        if (handle := match.group(1).rstrip(".").lower())
        and handle not in _NON_PROFILE_PATHS
    ]
    if not handles:
        return None
    return Counter(handles).most_common(1)[0][0]


async def find_instagram_handle(store_url: str) -> Optional[str]:
    """Scrape the store homepage for its Instagram link. Raises on network or
    HTTP errors so a blocked fetch isn't mistaken for "no Instagram link"."""
    parsed = urlparse(store_url)
    if not parsed.netloc:
        return None
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}/"
    async with httpx.AsyncClient(
        headers=_BROWSER_HEADERS, follow_redirects=True, timeout=10.0
    ) as http_client:
        response = await http_client.get(origin)
    response.raise_for_status()
    return extract_handle(response.text)


def _site_key(host: str) -> str:
    """The registrable part of a hostname, so shop.brand.com and www.brand.com
    compare equal: "brand.com" (or "brand.co.uk")."""
    labels = host.lower().removeprefix("www.").split(".")
    if (
        len(labels) >= 3
        and len(labels[-1]) == 2
        and labels[-2] in _SECOND_LEVEL_LABELS
    ):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _linked_sites(profile: dict[str, Any]) -> set[str]:
    """The sites (see _site_key) the profile's website links point to."""
    urls = [profile.get("externalUrl")] + [
        link.get("url") for link in profile.get("externalUrls") or []
    ]
    sites = set()
    for url in urls:
        if isinstance(url, str) and url:
            host = urlparse(url if "//" in url else f"//{url}").hostname
            if host:
                sites.add(_site_key(host))
    return sites


def _links_to_site(profile: dict[str, Any], site: str) -> bool:
    """Whether any website link on the profile points at the store's site."""
    return site in _linked_sites(profile)


def _website_match(profile: dict[str, Any], site: str) -> Optional[bool]:
    """Does the profile's website link back to the store? True if it does,
    False if it points at some other site (a sign the account isn't the
    store's, e.g. a page linking a reputable brand's Instagram to look
    legitimate), None if it has no website or only link-in-bio pages and
    social links, which prove nothing either way."""
    sites = _linked_sites(profile)
    if site in sites:
        return True
    return False if sites - _NEUTRAL_SITES else None


async def _run_actor(
    apify: ApifyClientAsync,
    run_input: dict[str, Any],
    max_items: int,
    *,
    allow_partial: bool = False,
) -> list[dict[str, Any]]:
    """Run the scraper and return its items. A run that hits its timeout has
    usually still saved what it scraped so far; that's only accepted with
    allow_partial, for callers where a partial result can't mislead."""
    run = await apify.actor(_ACTOR_ID).call(
        run_input=run_input,
        max_items=max_items,
        max_total_charge_usd=_MAX_CHARGE_USD,
        run_timeout=_RUN_TIMEOUT,
        logger=None,
    )
    timed_out = run is not None and run.status == "TIMED-OUT"
    if run is None or (run.status != "SUCCEEDED" and not (timed_out and allow_partial)):
        raise RuntimeError(f"Apify run did not succeed (status={run and run.status})")
    page = await apify.dataset(run.default_dataset_id).list_items(limit=max_items)
    if timed_out:
        if not page.items:
            raise RuntimeError("Apify run timed out before returning any results")
        logger.warning(
            "Apify run timed out; using its %d partial result(s)", len(page.items)
        )
    return page.items


async def find_profile_by_search(
    apify: ApifyClientAsync, brand: str, store_url: str
) -> Optional[dict[str, Any]]:
    """Search Instagram for the brand and return its profile details, but only
    if the profile's website link points at this store. Names alone match
    lookalike accounts (@lightintheboxfashion), and scoring the wrong account
    would be worse than scoring none.

    A timed-out run's partial results are fine here: each candidate is
    verified on its own, and the run tends to stall on its last profile after
    the useful ones are already saved."""
    site = _site_key(urlparse(store_url).hostname or "")
    items = await _run_actor(
        apify,
        {
            "search": brand,
            "searchType": "user",
            "searchLimit": SEARCH_LIMIT,
            "resultsType": "details",
            "resultsLimit": 1,
        },
        max_items=SEARCH_LIMIT,
        allow_partial=True,
    )
    matches = [
        item
        for item in items
        if item.get("username")
        and "followersCount" in item
        and _links_to_site(item, site)
    ]
    logger.info(
        "Instagram search for %r: %d candidate(s), %d link to %s",
        brand,
        len(items),
        len(matches),
        site,
    )
    return max(matches, key=lambda item: item["followersCount"], default=None)


async def _resolved(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return value


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_tags(items: list[dict[str, Any]], handle: str) -> list[InstagramTag]:
    tags = []
    for item in items:
        owner = (item.get("ownerUsername") or "").strip()
        # Error placeholders have no owner; the store tagging itself isn't proof.
        if not owner or owner.lower() == handle.lower():
            continue
        tags.append(
            InstagramTag(
                owner=owner,
                url=item.get("url"),
                timestamp=_parse_timestamp(item.get("timestamp")),
            )
        )
    return tags


def _skipped(
    reason: str,
    handle: Optional[str] = None,
    followers: Optional[int] = None,
    verified: bool = False,
) -> InstagramFindings:
    """An account-level outcome that leaves both signals unscored."""
    return InstagramFindings(
        handle=handle,
        followers=followers,
        verified=verified,
        skip_reason=reason,
        comments=CommentFindings(skip_reason=reason),
    )


async def research_instagram(
    apify: ApifyClientAsync,
    store_url: str,
    *,
    brand: Optional[str] = None,
    page_links: Sequence[str] = (),
) -> InstagramFindings:
    """Score the store's Instagram account on two signals: how much organic
    tagging it gets, and what the comments on its own posts say.

    The account is found from, in order: Instagram links the browser extension
    read off the live page (page_links), the store homepage's Instagram link,
    and, if the homepage can't be read or has none and a brand name is given,
    an Instagram search that accepts only a profile linking back to the store.
    Whatever the route, a profile whose website points at a different site is
    not scored: it may be a reputable account the page borrowed.

    Failures (network, Apify) raise, except a failed tags or posts run, which
    only marks its own signal as errored. "Nothing to score" outcomes come
    back as findings with skip_reason set.
    """
    handle = extract_handle("\n".join(page_links)) if page_links else None
    if handle:
        logger.info("Using the Instagram link @%s the page itself contained", handle)

    homepage_error: Optional[httpx.HTTPError] = None
    if handle is None:
        try:
            handle = await find_instagram_handle(store_url)
        except httpx.HTTPError as exc:
            # Storefronts often block scripted requests (403), so don't give up.
            logger.info("Couldn't read the homepage of %s: %s", store_url, exc)
            homepage_error = exc
    # handle = 'anniecloth_official'

    profile: Optional[dict[str, Any]] = None  # a search hit already has the details
    if handle is None and brand:
        try:
            profile = await find_profile_by_search(apify, brand, store_url)
        except Exception as exc:
            if homepage_error is not None:
                raise  # neither route worked, so this is a real failure
            # The homepage read fine and had no link; search was only a bonus.
            logger.warning("Instagram search for %r failed: %r", brand, exc)
        if profile is not None:
            handle = profile["username"]
            logger.info("Found Instagram profile @%s by searching %r", handle, brand)

    if handle is None:
        logger.info("No Instagram account found for %s", store_url)
        if homepage_error is None:
            return _skipped("no Instagram link found on the store's homepage")
        return _skipped(
            "couldn't read the store's homepage"
            + (" and found no Instagram profile linking to it" if brand else "")
        )

    profile_url = f"https://www.instagram.com/{handle}/"
    details_call = (
        _run_actor(
            apify,
            {"resultsType": "details", "directUrls": [profile_url], "resultsLimit": 1},
            max_items=1,
        )
        if profile is None
        else _resolved([profile])
    )
    details_items, tag_items, post_items = await asyncio.gather(
        details_call,
        _run_actor(
            apify,
            {
                "resultsType": "mentions",
                "directUrls": [profile_url],
                "resultsLimit": TAG_LIMIT,
            },
            max_items=TAG_LIMIT,
        ),
        # The comments score is a share of complaints, so a run that times out
        # after saving most of the posts still gives a usable (if slightly
        # noisier) answer. Tags are an absolute count and must not do this.
        _run_actor(
            apify,
            {
                "resultsType": "posts",
                "directUrls": [profile_url],
                "resultsLimit": POSTS_LIMIT,
            },
            max_items=POSTS_LIMIT,
            allow_partial=True,
        ),
        return_exceptions=True,
    )
    # Profile details are required: both signals need to know the account
    # exists and is public. The tags and posts runs each feed one signal, so
    # one failing (Instagram scrapes time out now and then) mustn't take the
    # other's score down with it.
    if isinstance(details_items, BaseException):
        raise details_items

    # A missing profile comes back as an error placeholder without followersCount.
    profile = next((i for i in details_items if "followersCount" in i), None)
    if profile is None:
        return _skipped(f"Instagram profile @{handle} not found", handle=handle)

    followers = int(profile["followersCount"])
    verified = bool(profile.get("verified"))
    if profile.get("private"):
        return _skipped(
            f"@{handle} is a private account",
            handle=handle,
            followers=followers,
            verified=verified,
        )

    site = _site_key(urlparse(store_url).hostname or "")
    website_match = _website_match(profile, site)
    if website_match is False:
        elsewhere = ", ".join(sorted(_linked_sites(profile) - _NEUTRAL_SITES)[:2])
        logger.warning(
            "Instagram @%s links to %s, not %s; not scoring it", handle, elsewhere, site
        )
        return _skipped(
            f"@{handle}'s website link points to {elsewhere}, not this store, so "
            "it may not be the store's own account",
            handle=handle,
            followers=followers,
            verified=verified,
        )

    base = InstagramFindings(
        handle=handle,
        followers=followers,
        verified=verified,
        website_match=website_match,
    )
    if isinstance(post_items, BaseException):
        logger.warning("Instagram posts run for @%s failed: %r", handle, post_items)
        base.comments = CommentFindings(error=f"posts run failed: {post_items}")
    else:
        base.comments = analyze_comments(parse_comments(post_items, handle))
        logger.info(
            "Instagram @%s: %d comment(s) analyzed, %d complaint(s), risk=%s",
            handle,
            base.comments.analyzed,
            len(base.comments.complaints),
            base.comments.risk_score,
        )

    # A tiny account can't be judged by its tags, but its comments still count.
    if followers < MIN_FOLLOWERS:
        base.skip_reason = f"@{handle} has too few followers ({followers}) to judge"
        return base

    if isinstance(tag_items, BaseException):
        logger.warning("Instagram tags run for @%s failed: %r", handle, tag_items)
        base.tags_error = f"tags run failed: {tag_items}"
        return base

    tags = _parse_tags(tag_items, handle)
    recent = count_recent_taggers(tags)
    logger.info(
        "Instagram @%s: %d followers, %d tag(s) fetched, %d distinct recent tagger(s)",
        handle,
        followers,
        len(tags),
        recent,
    )
    base.tags = tags
    base.recent_taggers = recent
    base.expected_taggers = expected_taggers(followers)
    base.risk_score = tag_risk_score(followers, recent)
    return base
