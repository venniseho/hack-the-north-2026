"""Entry point for the scam-check agent.

Owns the Backboard client's lifecycle and orchestrates the research tools
under agent/tools/ — each tool module takes a client rather than creating
its own, so this is the only place credentials and client config live.
"""

import asyncio
import os

from dotenv import load_dotenv
from backboard import BackboardClient

from .tools.reddit import research_reddit

load_dotenv()


def get_client() -> BackboardClient:
    api_key = os.environ.get("BACKBOARD_API_KEY")
    if not api_key:
        raise SystemExit(
            "BACKBOARD_API_KEY is not set in .env — add it before running this."
        )
    return BackboardClient(api_key=api_key)


async def main() -> None:
    client = get_client()

    findings = await research_reddit(client, brand="Azazie", domain="https://www.azazie.ca/?srsltid=AU7gw4Uqs4j_fNGGPQmIFNI6USu-DN7dAvGngMztzcouoTTqkl_VOxx_")

    print(f"found_any: {findings.found_any}")
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


if __name__ == "__main__":
    asyncio.run(main())
