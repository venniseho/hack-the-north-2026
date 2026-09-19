"""GPTZero scoring: one review in, one score out.

Measured against the live API (2026-09-19) rather than assumed:

* There is no minimum length. A 13-character document returns HTTP 200 with a
  full score, so the "~250 characters" figure in GPTZero's docs is a guideline
  about reliability, not a limit.
* It discriminates fine on short review text. Real scraped Trustpilot reviews
  of 35-131 chars scored 0.001-0.008 ("human"); synthetic marketing slop of
  118-158 chars scored 1.000 ("ai").
* Scores are bimodal - near 0 or near 1, with little in between - so the useful
  aggregate is "what share of reviews were flagged", not a mean probability.
* It misses some. One of four synthetic slop reviews came back 0.008. Judge a
  store on many reviews, never on one.
* The API reports its own confidence (`confidence_category`, `predicted_class`),
  so there is no need to estimate it from text length.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import re
import statistics
from dataclasses import dataclass, field

import httpx

API_URL = "https://api.gptzero.me/v2/predict/text"

# A review at or above this probability counts as AI-written. The API's own
# scores are bimodal, so anything in 0.5-0.9 works identically on real data.
AI_THRESHOLD = 0.65

# Not a hard floor (see module docstring) - just the length below which
# GPTZero's own docs stop promising reliability. Recorded per review so the UI
# can show which findings rest on thin text.
RELIABLE_CHARS = 250


@dataclass
class ReviewScore:
    """One review's result."""

    text: str
    ai_prob: float
    predicted_class: str  # 'human' | 'ai' | 'mixed'
    confidence: str  # 'high' | 'medium' | 'low'
    error: str | None = None

    @property
    def is_ai(self) -> bool:
        return self.ai_prob >= AI_THRESHOLD

    @property
    def is_short(self) -> bool:
        return len(self.text) < RELIABLE_CHARS


@dataclass
class CorpusVerdict:
    """The aggregate over every review from one store."""

    total: int
    scored: int
    flagged: int
    ai_share: float
    mean_prob: float
    short_flagged: int
    verdict: str  # 'likely_ai_reviews' | 'mixed' | 'likely_human' | 'unknown'
    confidence: str  # 'high' | 'medium' | 'low' | 'insufficient'
    scores: list[ReviewScore] = field(default_factory=list)


class GPTZeroClient:
    def __init__(self, api_key: str, concurrency: int = 4) -> None:
        self._key = api_key
        self._http: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(concurrency)
        self._cache: dict[str, ReviewScore] = {}

    async def __aenter__(self) -> GPTZeroClient:
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_connections=8),
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def score(self, text: str) -> ReviewScore:
        """Score a single review."""
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]

        async with self._sem:
            result = await self._request(text)

        self._cache[key] = result
        return result

    async def score_all(self, texts: list[str]) -> list[ReviewScore]:
        return list(await asyncio.gather(*(self.score(t) for t in texts)))

    async def _request(self, text: str) -> ReviewScore:
        assert self._http is not None, "use GPTZeroClient as an async context manager"
        headers = {"x-api-key": self._key, "Content-Type": "application/json"}

        for attempt in range(3):
            try:
                resp = await self._http.post(
                    API_URL, json={"document": text}, headers=headers
                )
            except httpx.TransportError as exc:
                if attempt == 2:
                    return _failed(text, f"transport error: {exc}")
                await _backoff(attempt, None)
                continue

            if resp.status_code == 200:
                return _parse(text, resp.json())
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == 2:
                    return _failed(text, f"HTTP {resp.status_code}")
                await _backoff(attempt, resp.headers.get("Retry-After"))
                continue
            return _failed(text, f"HTTP {resp.status_code}: {resp.text[:120]}")

        return _failed(text, "retries exhausted")


async def _backoff(attempt: int, retry_after: str | None) -> None:
    if retry_after:
        try:
            await asyncio.sleep(min(float(retry_after), 10.0))
            return
        except ValueError:
            pass
    await asyncio.sleep(0.5 * 2**attempt + random.random() * 0.3)


def _parse(text: str, payload: dict) -> ReviewScore:
    docs = payload.get("documents") or []
    if not docs:
        return _failed(text, "no documents in response")
    doc = docs[0]
    return ReviewScore(
        text=text,
        ai_prob=float(doc.get("completely_generated_prob") or 0.0),
        predicted_class=str(doc.get("predicted_class") or "unknown"),
        confidence=str(doc.get("confidence_category") or "unknown"),
    )


def _failed(text: str, error: str) -> ReviewScore:
    return ReviewScore(
        text=text,
        ai_prob=0.0,
        predicted_class="unknown",
        confidence="unknown",
        error=error,
    )


# ----------------------------------------------------------------------
# aggregation
# ----------------------------------------------------------------------


def summarize(scores: list[ReviewScore]) -> CorpusVerdict:
    """Aggregate per-review scores into a store-level verdict.

    Uses the share of reviews flagged rather than the mean probability: the
    API's scores are bimodal, so a mean is dragged around by how many reviews
    happen to be clean and says less than the count does.
    """
    usable = [s for s in scores if s.error is None]
    flagged = [s for s in usable if s.is_ai]
    ai_share = len(flagged) / len(usable) if usable else 0.0
    mean_prob = statistics.fmean([s.ai_prob for s in usable]) if usable else 0.0

    confidence = _confidence(len(usable), flagged)
    if confidence == "insufficient":
        verdict = "unknown"
    elif ai_share >= 0.40:
        verdict = "likely_ai_reviews"
    elif ai_share >= 0.15:
        verdict = "mixed"
    else:
        verdict = "likely_human"

    return CorpusVerdict(
        total=len(scores),
        scored=len(usable),
        flagged=len(flagged),
        ai_share=round(ai_share, 4),
        mean_prob=round(mean_prob, 4),
        short_flagged=sum(1 for s in flagged if s.is_short),
        verdict=verdict,
        confidence=confidence,
        scores=sorted(scores, key=lambda s: s.ai_prob, reverse=True),
    )


def _confidence(n_usable: int, flagged: list[ReviewScore]) -> str:
    if n_usable < 3:
        return "insufficient"
    # A verdict resting only on sub-250-char reviews is the case GPTZero's own
    # docs caution about, so say so rather than burying it.
    if flagged and all(s.is_short for s in flagged):
        return "low"
    if n_usable >= 15:
        return "high"
    if n_usable >= 8:
        return "medium"
    return "low"
