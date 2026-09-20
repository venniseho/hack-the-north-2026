"""Entry point for the scam-check agent.

Owns the Backboard client's lifecycle and orchestrates the research tools
under agent/tools/ — each tool module takes a client rather than creating
its own, so this is the only place credentials and client config live.
"""

import asyncio
import logging
import os
import time
from collections.abc import Sequence
from urllib.parse import urlparse

from apify_client import ApifyClientAsync
from dotenv import load_dotenv
from backboard import BackboardClient

from .tools.instagram import InstagramFindings, research_instagram
from .tools.reddit import RedditFindings, research_reddit

load_dotenv()

# uvicorn only configures its own loggers, so without a root handler our INFO
# logs would vanish. Only the "backend" tree gets LOG_LEVEL, which keeps httpx
# and other libraries at their default WARNING.
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("backend").setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

RESEARCH_TIMEOUT_SECONDS = 45.0
CACHE_TTL_SECONDS = 1

# A research run is two LLM calls plus a web search, so repeat checks of the
# same store are served from memory. Only successful runs are cached.
_cache: dict[str, tuple[float, RedditFindings]] = {}
_client: BackboardClient | None = None

# Worst case: a homepage fetch (10s), then an Instagram search when the
# homepage is blocked (one 60s run), then two parallel runs (60s), then the
# comment review (30s). Typical is far shorter. Every cache miss spends Apify
# credit, hence the long TTL.
INSTAGRAM_TIMEOUT_SECONDS = 160.0
INSTAGRAM_CACHE_TTL_SECONDS = 6 * 60 * 60
_instagram_cache: dict[str, tuple[float, InstagramFindings]] = {}
_apify_client: ApifyClientAsync | None = None

# Second-level labels that pair with a country TLD (shop.co.uk -> "shop").
_SECOND_LEVEL_LABELS = {"co", "com", "org", "net", "gov", "ac"}


def get_client() -> BackboardClient:
    global _client
    if _client is None:
        api_key = os.environ.get("BACKBOARD_API_KEY")
        if not api_key:
            raise RuntimeError(
                "BACKBOARD_API_KEY is not set in .env — add it before running this."
            )
        _client = BackboardClient(api_key=api_key)
    return _client


def get_apify_client() -> ApifyClientAsync:
    global _apify_client
    if _apify_client is None:
        token = os.environ.get("APIFY_API_TOKEN")
        if not token:
            raise RuntimeError(
                "APIFY_API_TOKEN is not set in .env — add it before running this."
            )
        _apify_client = ApifyClientAsync(token)
    return _apify_client


def domain_from_url(current_url: str) -> str:
    """Bare hostname without "www." — drops the path and tracking params."""
    hostname = urlparse(current_url).hostname or current_url
    return hostname.removeprefix("www.")


def brand_from_domain(domain: str) -> str:
    """Best-effort store name from a hostname: azazie.ca -> "Azazie"."""
    labels = domain.split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL_LABELS:
        name = labels[-3]
    elif len(labels) >= 2:
        name = labels[-2]
    else:
        name = labels[0]
    return name.replace("-", " ").title()


async def research_store(current_url: str) -> RedditFindings:
    """Research the store behind current_url. Never raises: failures come back
    as RedditFindings with error set, so one broken source can't fail /analyze."""
    domain = domain_from_url(current_url)

    cached = _cache.get(domain)
    if cached is not None and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        logger.info("Serving cached Reddit research for %s", domain)
        return cached[1]

    try:
        findings = await asyncio.wait_for(
            research_reddit(
                get_client(), brand=brand_from_domain(domain), domain=domain
            ),
            timeout=RESEARCH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Reddit research for %s timed out after %.0fs",
            domain,
            RESEARCH_TIMEOUT_SECONDS,
        )
        return RedditFindings(
            found_any=False,
            error=f"research timed out after {RESEARCH_TIMEOUT_SECONDS:.0f}s",
        )
    except Exception as exc:
        logger.exception("Reddit research for %s failed", domain)
        return RedditFindings(found_any=False, error=f"research failed: {exc}")

    if findings.error is None:
        _cache[domain] = (time.monotonic(), findings)
    return findings


async def research_store_instagram(
    current_url: str, instagram_links: Sequence[str] = ()
) -> InstagramFindings:
    """Check the comments on the store's Instagram posts.
    instagram_links are Instagram URLs the browser extension read off the page.
    Never raises: failures come back as InstagramFindings with error set."""
    domain = domain_from_url(current_url)

    cached = _instagram_cache.get(domain)
    if (
        cached is not None
        and time.monotonic() - cached[0] < INSTAGRAM_CACHE_TTL_SECONDS
    ):
        logger.info("Serving cached Instagram research for %s", domain)
        return cached[1]

    try:
        findings = await asyncio.wait_for(
            research_instagram(
                get_apify_client(),
                get_client(),
                current_url,
                brand=brand_from_domain(domain),
                page_links=instagram_links,
            ),
            timeout=INSTAGRAM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Instagram research for %s timed out after %.0fs",
            domain,
            INSTAGRAM_TIMEOUT_SECONDS,
        )
        return InstagramFindings(
            error=f"research timed out after {INSTAGRAM_TIMEOUT_SECONDS:.0f}s"
        )
    except Exception as exc:
        logger.exception("Instagram research for %s failed", domain)
        return InstagramFindings(error=f"research failed: {exc}")

    _instagram_cache[domain] = (time.monotonic(), findings)
    return findings


async def main() -> None:
    findings = await research_store(
        "https://www.azazie.ca/?srsltid=AU7gw4Uqs4j_fNGGPQmIFNI6USu-DN7dAvGngMztzcouoTTqkl_VOxx_"
    )

    print(f"found_any: {findings.found_any}")
    print(f"risk_score: {findings.risk_score}")
    print(f"thread_id: {findings.thread_id}")
    if findings.error:
        print(f"error: {findings.error}")
    print(f"\n{len(findings.posts)} verified post(s):")
    for post in findings.posts:
        print(f"  [{post.severity}] {post.title}")
        print(f"    r/{post.subreddit}  {post.url}")
        print(f'    "{post.quote}"')
    print("\n--- raw research turn ---")
    print(findings.raw_research)
    print(f"risk_score: {findings.risk_score}")


if __name__ == "__main__":
    asyncio.run(main())
