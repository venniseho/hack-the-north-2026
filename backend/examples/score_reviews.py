#!/usr/bin/env python3
"""Run the GPTZero scorer over sample reviews and print what it decided.

    cd backend
    python examples/score_reviews.py                 # every group
    python examples/score_reviews.py capatee.com     # one group
    python examples/score_reviews.py --text "..."    # score one ad-hoc string

Needs GPTZERO_API_KEY in backend/.env.

Sample data lives in examples/sample_reviews.json: verbatim Trustpilot reviews
for a blocklisted storefront and an established brand, plus a synthetic group
of LLM-style filler as a positive control. If the control does not light up,
the run is broken - that is what it is there for.

Reading the output: `share flagged` is the number that matters. GPTZero's
scores are close to 0 or 1 with little in between, so the count of flagged
reviews carries the signal and the mean probability mostly does not.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Allow running as `python examples/score_reviews.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from services.gptzero import (  # noqa: E402
    RELIABLE_CHARS,
    CorpusVerdict,
    GPTZeroClient,
    ReviewScore,
    summarize,
)

SAMPLES = Path(__file__).parent / "sample_reviews.json"

GREEN, YELLOW, RED, GREY, BOLD, OFF = (
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[90m",
    "\033[1m",
    "\033[0m",
)
VERDICT_COLOR = {
    "likely_ai_reviews": RED,
    "mixed": YELLOW,
    "likely_human": GREEN,
    "unknown": GREY,
}


def make_client() -> GPTZeroClient:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    key = os.environ.get("GPTZERO_API_KEY", "")
    if not key:
        raise SystemExit(
            "GPTZERO_API_KEY is not set. Add it to backend/.env and try again."
        )
    return GPTZeroClient(key)


def print_score(score: ReviewScore) -> None:
    if score.error:
        print(f"  {GREY}{len(score.text):5d}ch  ERROR  {score.error}{OFF}")
        return

    color = RED if score.is_ai else GREEN
    short = f" {YELLOW}short{OFF}" if score.is_short else "     "
    excerpt = score.text[:62].replace("\n", " ")
    print(
        f"  {len(score.text):5d}ch  {color}{score.ai_prob:6.3f}{OFF}  "
        f"{score.predicted_class:<7} {score.confidence:<6}{short}  {excerpt!r}"
    )


def print_verdict(name: str, note: str, verdict: CorpusVerdict) -> None:
    color = VERDICT_COLOR.get(verdict.verdict, GREY)
    print(f"\n{BOLD}{'=' * 78}{OFF}")
    print(f"{BOLD}{name}{OFF}")
    print(f"{GREY}{note}{OFF}")
    print(f"{BOLD}{'=' * 78}{OFF}")

    for score in verdict.scores:
        print_score(score)

    print()
    print(f"  verdict        {color}{BOLD}{verdict.verdict}{OFF} ({verdict.confidence} confidence)")
    print(f"  share flagged  {verdict.ai_share:.0%}  ({verdict.flagged}/{verdict.scored} reviews)")
    print(f"  mean prob      {verdict.mean_prob:.3f}")
    if verdict.short_flagged:
        print(
            f"  {YELLOW}caution{OFF}        {verdict.short_flagged} of {verdict.flagged} "
            f"flagged reviews are under {RELIABLE_CHARS} chars"
        )
    if verdict.scored < verdict.total:
        print(f"  {GREY}unscored       {verdict.total - verdict.scored}{OFF}")


async def run_groups(wanted: list[str]) -> int:
    data = json.loads(SAMPLES.read_text())
    groups = data["groups"]
    if wanted:
        groups = [g for g in groups if g["name"] in wanted]
        if not groups:
            names = ", ".join(g["name"] for g in data["groups"])
            print(f"No group matched {wanted}. Available: {names}", file=sys.stderr)
            return 2

    client = make_client()
    results: list[tuple[str, str, CorpusVerdict]] = []
    async with client:
        for group in groups:
            scores = await client.score_all([r["text"] for r in group["reviews"]])
            verdict = summarize(scores)
            results.append((group["name"], group["label"], verdict))
            print_verdict(group["name"], group["note"], verdict)

    print(f"\n{BOLD}{'=' * 78}\nsummary\n{'=' * 78}{OFF}")
    width = max(len("group"), *(len(n) for n, _, _ in results)) + 2
    print(f"  {'group':<{width}}{'label':<12}{'flagged':<14}{'verdict'}")
    for name, label, verdict in results:
        color = VERDICT_COLOR.get(verdict.verdict, GREY)
        flagged = f"{verdict.flagged}/{verdict.scored} ({verdict.ai_share:.0%})"
        print(f"  {name:<{width}}{label:<12}{flagged:<14}{color}{verdict.verdict}{OFF}")

    # The synthetic control exists to catch a silently broken run.
    control = next((v for n, lab, v in results if lab == "ai_control"), None)
    if control is not None and control.flagged == 0:
        print(
            f"\n{RED}Control group flagged nothing. The scorer is probably not "
            f"working - check the API key and the response shape.{OFF}"
        )
        return 1
    return 0


async def run_text(text: str) -> int:
    async with make_client() as client:
        print_score(await client.score(text))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", help="group names to run (default: all)")
    parser.add_argument("--text", help="score a single string instead")
    args = parser.parse_args()

    if args.text:
        return asyncio.run(run_text(args.text))
    return asyncio.run(run_groups(args.groups))


if __name__ == "__main__":
    raise SystemExit(main())
