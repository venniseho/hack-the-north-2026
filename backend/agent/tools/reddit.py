"""Reddit evidence gathering via Backboard's web_search sources."""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Literal, Optional, cast, get_args

import httpx
from backboard import BackboardClient
from backboard.models import ChatMessagesResponse

Severity = Literal["critical", "major", "moderate", "minor", "positive"]

_SEVERITIES: tuple[str, ...] = get_args(Severity)

_PERMALINK_RE = re.compile(
    r"^https?://(www\.|old\.)?reddit\.com/r/[^/]+/comments/[a-z0-9]+/",
    re.IGNORECASE,
)

# Each negative post keeps this fraction of the current trust (0-100), so
# penalties compound with diminishing effect and trust never hits 0.
_SEVERITY_FACTOR: dict[str, float] = {
    "critical": 0.60,
    "major": 0.75,
    "moderate": 0.85,
    "minor": 0.97,
}
_POSITIVE_GAP_CLOSE = 0.10  # each positive post closes this share of the trust gap to 100


@dataclass
class RedditPost:
    url: str
    title: str
    quote: str
    severity: Severity
    subreddit: Optional[str] = None
    verified: bool = False  # True only if we could confirm the URL resolves


@dataclass
class RedditFindings:
    found_any: bool
    posts: list[RedditPost] = field(default_factory=list)
    thread_id: Optional[str] = None
    raw_research: Optional[str] = None
    error: Optional[str] = None
    risk_score: Optional[int] = None  # 0-100, higher is riskier; None if research failed or found no posts


_RESEARCH_SYSTEM_PROMPT = (
    "You investigate whether online stores are scams. When you search, restrict "
    "your queries to Reddit using site:reddit.com. For every relevant result, report: "
    "the post title, the subreddit if visible, a short direct quote, and the exact URL "
    "as returned by search — never guess, construct, or complete a URL. If nothing "
    "relevant turns up, say so explicitly rather than inventing results."
)

_EXTRACTION_INSTRUCTIONS = (
    'Extract your Reddit findings above into this exact JSON shape: '
    '{"found_any": bool, "posts": [{"url": str, "title": str, "subreddit": str or null, '
    '"quote": str, "severity": "critical" | "major" | "moderate" | "minor" | "positive"}]}. '
    "Severity describes the harm the post reports: "
    "critical = non-delivery, fraudulent charges, counterfeit or fake goods; "
    "major = product materially worse than or different from how it was advertised "
    "(e.g. very poor quality vs. photos), bait-and-switch, refund or chargeback refused; "
    "moderate = return/refund obstruction, unresponsive support, hidden fees or "
    "subscriptions, shipping far later than promised; "
    "minor = isolated defect, sizing issue, or a resolved one-off problem; "
    "positive = a genuine good experience with no reported problem. "
    "If you found nothing relevant, return an empty posts array and found_any: false."
)


def score_reddit(posts: list[RedditPost]) -> int:
    """Risk score 0-100 (higher is riskier) from Reddit posts.

    Internally computes trust T = 100 * prod(severity factors), then closes a
    share g of the gap to 100 per positive post: T' = T + (100 - T) * (1 - (1 - g)^n).
    Returns 100 - T'. Positives are applied after all negatives, so post order
    doesn't matter.
    """
    trust = 100.0
    for post in posts:
        trust *= _SEVERITY_FACTOR.get(post.severity, 1.0)
    positives = sum(post.severity == "positive" for post in posts)
    trust += (100 - trust) * (1 - (1 - _POSITIVE_GAP_CLOSE) ** positives)
    return round(100 - trust)


async def _verify_url(client: httpx.AsyncClient, url: str) -> bool:
    """Best-effort check that a URL isn't fabricated.
    """
    try:
        resp = await client.head(url, follow_redirects=True, timeout=5.0)
        return resp.status_code != 404
    except httpx.HTTPError:
        return True  # don't punish the post for a blocked request


async def research_reddit(
    client: BackboardClient,
    brand: str,
    domain: str,
    *,
    llm_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    verify_urls: bool = True,
) -> RedditFindings:
    """Gather Reddit evidence about a brand/domain using Backboard web_search.

    Two calls on the same thread:
      1. web_search=Auto — the model researches Reddit and replies in prose.
      2. json_output=True — the model extracts its own prior answer into
         structured JSON (web_search and json_output can't both be active
         on one turn, per Backboard's docs).
    """
    research = cast(
        ChatMessagesResponse,
        await client.send_message(
            f'Research Reddit for scam reports or trustworthy discussion about '
            f'"{brand}" ({domain}). Look for posts warning about non-delivery, '
            f"counterfeit products, fraud, products far worse than advertised, or "
            f"refund problems, and also genuine positive experiences if they exist.",
            system_prompt=_RESEARCH_SYSTEM_PROMPT,
            web_search="Auto",
            llm_provider=llm_provider,
            model_name=model_name,
        ),
    )

    if not research.content:
        return RedditFindings(found_any=False, error="empty research response")

    extraction = cast(
        ChatMessagesResponse,
        await client.send_message(
            _EXTRACTION_INSTRUCTIONS,
            thread_id=research.thread_id,
            json_output=True,
            llm_provider=llm_provider,
            model_name=model_name,
        ),
    )

    if not extraction.content:
        return RedditFindings(
            found_any=False,
            thread_id=research.thread_id,
            raw_research=research.content,
            error="empty extraction response",
        )

    try:
        parsed = json.loads(extraction.content)
    except json.JSONDecodeError as exc:
        return RedditFindings(
            found_any=False,
            thread_id=research.thread_id,
            raw_research=research.content,
            error=f"failed to parse extraction JSON: {exc}",
        )

    posts: list[RedditPost] = []
    for raw_post in parsed.get("posts", []):
        url = (raw_post.get("url") or "").strip()
        if not url or not _PERMALINK_RE.match(url):
            continue  # not a real-looking Reddit permalink — likely hallucinated
        severity = raw_post.get("severity")
        if severity not in _SEVERITIES:
            severity = "minor"  # unlabeled/invalid: keep the post, weight it lightly
        posts.append(
            RedditPost(
                url=url,
                title=raw_post.get("title", ""),
                quote=raw_post.get("quote", ""),
                severity=severity,
                subreddit=raw_post.get("subreddit"),
            )
        )

    if verify_urls and posts:
        async with httpx.AsyncClient(
            headers={"User-Agent": "scamcheck-hackathon/0.1 (link verification)"}
        ) as http_client:
            results = await asyncio.gather(
                *(_verify_url(http_client, p.url) for p in posts)
            )
        for post, ok in zip(posts, results):
            post.verified = ok
        posts = [p for p in posts if p.verified]

    return RedditFindings(
        found_any=bool(parsed.get("found_any", bool(posts))),
        posts=posts,
        thread_id=research.thread_id,
        raw_research=research.content,
        risk_score=score_reddit(posts) if posts else None,
    )
