"""Entry point for the scam-check agent.

Owns the Backboard client's lifecycle and orchestrates the research tools
under agent/tools/ — each tool module takes a client rather than creating
its own, so this is the only place credentials and client config live.
"""

import asyncio
import os
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
from backboard import BackboardClient

from .tools.reddit import RedditFindings, research_reddit

load_dotenv()

RESEARCH_TIMEOUT_SECONDS = 45.0
CACHE_TTL_SECONDS = 15 * 60

# A research run is two LLM calls plus a web search, so repeat checks of the
# same store are served from memory. Only successful runs are cached.
_cache: dict[str, tuple[float, RedditFindings]] = {}
_client: BackboardClient | None = None

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
        return cached[1]

    try:
        findings = await asyncio.wait_for(
            research_reddit(
                get_client(), brand=brand_from_domain(domain), domain=domain
            ),
            timeout=RESEARCH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return RedditFindings(
            found_any=False,
            error=f"research timed out after {RESEARCH_TIMEOUT_SECONDS:.0f}s",
        )
    except Exception as exc:
        return RedditFindings(found_any=False, error=f"research failed: {exc}")

    if findings.error is None:
        _cache[domain] = (time.monotonic(), findings)
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
