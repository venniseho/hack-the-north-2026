"""Turn raw extracted review strings into something worth paying GPTZero for.

This is the join between the extraction side (the content script, or the
Playwright harness in `research/ai-review-detection/pipeline.py`) and
`services.gptzero`. It owns four things, in this order:

    normalise -> length filter -> dedupe -> cap

and one thing after scoring: downgrading the verdict's confidence when the
*extraction* was weak, which `summarize()` cannot know about.

Every step here exists because of a measured failure, documented in
`docs/ai-review-detection.md`:

* **Dedupe.** qenova.com's four JSON-LD `reviewBody` entries were the same
  review four times. Un-deduped, one AI-ish review becomes "4/4 flagged, 100%
  AI" - the most likely way this feature ships a confidently wrong verdict.
* **Cap.** Each review is a billed API call and `summarize()` reaches `high`
  confidence at 15 usable reviews, so more than ~30 buys nothing.
* **Length floor.** "Great!" and "A+++" carry no signal; a flag on one is noise.
* **Extraction confidence.** A corpus from the gated heuristic is a guess, and
  a corpus from SEO JSON-LD is a sample the *store* chose. Both can be right,
  neither deserves `high`.

THE HARD CONSTRAINT: nothing in this module may rewrite review prose. No
spell-correction, no tidying, and above all no LLM pass. Measured: one LLM pass
over six genuine human reviews moved them from 0% flagged to 100% flagged.
GPTZero scores the text you hand it, so the text must be the user's, typos and
all. `normalise()` only removes widget chrome and collapses whitespace.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace

from ...services.gptzero import CorpusVerdict, GPTZeroClient, summarize

# Mirrors `keep()` in frontend/public/extract-reviews.js. Kept in
# sync deliberately: the content script filters before it sends, and this is the
# backstop for anything that arrives by another path (JSON-LD, a hand-made
# fixture, a future API caller).
MIN_CHARS = 25
MAX_CHARS = 5000

# Per-store ceiling on billed calls. See the module docstring.
DEFAULT_CAP = 25

# Extraction sources whose output is real but unrepresentative, keyed to the
# `via` string that extract-reviews.js reports.
#
#   heuristic  - an unrecognised widget; the gates make this rarely wrong, but
#                it is still a guess about what counts as a review.
#   json-ld    - SEO markup, which exists to win rich snippets. The store picks
#                which reviews go in it, so it is a biased sample.
#   mixed-thin - fewer than 3 from any single source, merged to scrape together
#                a corpus.
WEAK_EXTRACTION = frozenset({"heuristic", "json-ld", "mixed-thin"})

_CONFIDENCE_ORDER = ("insufficient", "low", "medium", "high")

# --- normalisation --------------------------------------------------------
#
# Widget chrome that shares a text node with the review. extract-reviews.js
# strips these in the browser; repeating the cheap ones here means a corpus that
# arrived some other way is not scored with "Verified Purchase" glued to it.

_WHITESPACE = re.compile(r"\s+")
_STARS = re.compile(r"[★☆�]+")
_RATING = re.compile(r"\b\d(?:\.\d)?\s*out of\s*\d\s*stars?\b", re.IGNORECASE)
_LEADING_CHROME = re.compile(
    r"^(Verified Purchase|Verified Buyer|Verified Review|Translated from \w+)[:\s-]*",
    re.IGNORECASE,
)
_TRAILING_CHROME = re.compile(
    r"\s*(Was this helpful\?|Report abuse|Read more|Show less|Helpful\s*\(?\s*\d*\s*\)?)\s*$",
    re.IGNORECASE,
)
_EDGE_QUOTES = re.compile(r'^["“”\'\s]+|["“”\'\s]+$')

# Dedupe key: ignore case, punctuation and spacing, because the same review
# reached us twice through different widgets with different chrome stripped.
_KEY_NOISE = re.compile(r"[^a-z0-9]+")


def normalise(text: str) -> str:
    """Strip widget chrome and collapse whitespace. Never alters prose."""
    out = _WHITESPACE.sub(" ", text or "").strip()
    out = _STARS.sub(" ", out)
    out = _RATING.sub(" ", out)
    out = _LEADING_CHROME.sub("", out)
    out = _TRAILING_CHROME.sub("", out)
    out = _EDGE_QUOTES.sub("", out)
    return _WHITESPACE.sub(" ", out).strip()


def dedupe_key(text: str) -> str:
    """Content hash used to decide two strings are the same review."""
    return hashlib.sha256(_KEY_NOISE.sub("", text.lower()).encode()).hexdigest()


@dataclass
class PreparedReviews:
    """What survived, and what didn't - so the caller can say so out loud.

    The dropped counts are not diagnostics for us, they are the difference
    between "this store has 3 reviews" and "this store has 40 reviews, 37 of
    which were the same sentence".
    """

    texts: list[str] = field(default_factory=list)
    received: int = 0
    dropped_short: int = 0
    dropped_long: int = 0
    dropped_duplicate: int = 0
    dropped_to_cap: int = 0

    @property
    def usable(self) -> int:
        return len(self.texts)


def prepare(raw: list[str], *, cap: int = DEFAULT_CAP) -> PreparedReviews:
    """normalise -> length filter -> dedupe -> cap.

    Dedupe runs before the cap on purpose: capping first would spend the whole
    budget on repeats of one review and then report high confidence in it.
    """
    result = PreparedReviews(received=len(raw))
    seen: set[str] = set()

    for item in raw:
        text = normalise(item)
        if len(text) < MIN_CHARS:
            result.dropped_short += 1
            continue
        if len(text) > MAX_CHARS:
            # Almost always a container that swallowed a whole review list.
            # Truncating would hand GPTZero a Frankenstein document.
            result.dropped_long += 1
            continue

        key = dedupe_key(text)
        if key in seen:
            result.dropped_duplicate += 1
            continue
        seen.add(key)
        result.texts.append(text)

    if cap is not None and len(result.texts) > cap:
        result.dropped_to_cap = len(result.texts) - cap
        result.texts = result.texts[:cap]

    return result


def cap_confidence(verdict: CorpusVerdict, via: str | None) -> CorpusVerdict:
    """Downgrade confidence when the *extraction* was weak.

    `summarize()` reasons about the scores it was given; it has no idea whether
    those strings came from a widget selector or from a heuristic's best guess.
    A `low` ceiling for the weak sources keeps an unrepresentative corpus from
    reading as authoritatively as a clean one in the side panel.
    """
    if via not in WEAK_EXTRACTION:
        return verdict
    if verdict.confidence not in _CONFIDENCE_ORDER:
        return verdict
    if _CONFIDENCE_ORDER.index(verdict.confidence) <= _CONFIDENCE_ORDER.index("low"):
        return verdict  # already at or below the ceiling (incl. 'insufficient')
    return replace(verdict, confidence="low")


async def score_reviews(
    raw: list[str],
    *,
    api_key: str,
    via: str | None = None,
    cap: int = DEFAULT_CAP,
) -> tuple[CorpusVerdict, PreparedReviews]:
    """Prepare a raw corpus, score it, and return the verdict plus the audit.

    `via` is the extraction source reported by extract-reviews.js; pass it
    through so a heuristic or JSON-LD corpus gets its confidence capped.
    """
    prepared = prepare(raw, cap=cap)
    if not prepared.texts:
        return summarize([]), prepared

    async with GPTZeroClient(api_key) as client:
        scores = await client.score_all(prepared.texts)

    return cap_confidence(summarize(scores), via), prepared
