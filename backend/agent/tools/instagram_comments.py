"""Signals from the comments on a store's own Instagram posts.

Two things are worth catching: customers warning others off (complaints), and
engagement that looks manufactured (the same comment from many accounts). Both
are deterministic text heuristics rather than an LLM call, so they're cheap,
explainable and testable — but they miss sarcasm and nuance.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

# With too few comments, one angry customer or one bot swings the verdict.
MIN_COMMENTS = 10
# A single unhappy customer is normal for any brand; it takes a pattern.
MIN_COMPLAINTS = 2
COMPLAINT_SHARE_FOR_MAX_RISK = 0.25
COMPLAINT_MAX_RISK = 95

# The same comment from several different accounts looks manufactured. Short
# ones ("love it") repeat naturally, and emoji-only ones normalize to "".
DUPLICATE_MIN_AUTHORS = 3
DUPLICATE_MIN_LENGTH = 12
DUPLICATE_SHARE_FOR_MAX_RISK = 0.20
# Weaker evidence than customers saying they were scammed, so a lower ceiling.
DUPLICATE_MAX_RISK = 70

_COMPLAINT_PATTERNS = (
    # Outright scam language
    r"scam\w*", r"fraud\w*", r"fake", r"counterfeit",
    r"rip(?:s|ped|ping)?[- ]?(?:(?:you|me|us|people|customers) )?off",
    r"stole|stolen", r"thie(?:f|ves)", r"crooks?", r"liars?", r"lies|lying|lied|a lie",
    r"beware",
    # Non-delivery and refund trouble
    r"(?:never|didn'?t|did not|haven'?t|have not|hasn'?t|has not) "
    r"(?:arrive|arrived|receive|received|get|got|ship|shipped|come|came|show|showed)",
    r"still waiting", r"no refund", r"refus\w* (?:to )?(?:refund|return)",
    r"chargeback",
    # Warnings to other shoppers
    r"waste (?:of )?(?:my )?(?:time|money)", r"don'?t waste",
    r"(?:don'?t|do not|never) (?:buy|order|shop|purchase)", r"stay away",
    r"avoid (?:this|them|at all)",
    # Product worse than advertised
    r"worst", r"terrible", r"horrible", r"awful", r"disappointed",
    r"disgusting", r"pathetic", r"useless", r"garbage|trash|junk|crap",
    r"pieces? of (?:shit|crap|garbage|junk|trash)",
    r"poor quality", r"cheap(?:ly)? made",
    r"nothing like (?:the )?(?:pic|photo|ad|image)\w*",
    r"not as (?:advertised|pictured|described|shown)",
    r"not (?:correct|accurate|true)",
)  # fmt: skip
_COMPLAINT_RE = re.compile(
    r"\b(?:" + "|".join(_COMPLAINT_PATTERNS) + r")\b", re.IGNORECASE
)
# "This is not a scam" is praise, so strip those phrases before matching.
_NEGATED_SCAM_RE = re.compile(
    r"\b(?:not|isn'?t|is not|no|never)\s+(?:a\s+)?(?:scam|fraud|fake)\w*",
    re.IGNORECASE,
)


@dataclass
class InstagramComment:
    owner: str
    text: str
    post_url: Optional[str] = None


@dataclass
class CommentFindings:
    analyzed: int = 0
    complaints: list[InstagramComment] = field(default_factory=list)
    complaint_risk: int = 0
    duplicate_comments: int = 0  # comments whose text several accounts repeated
    duplicate_risk: int = 0
    # Why no score was produced when nothing went wrong (private, too few comments).
    skip_reason: Optional[str] = None
    error: Optional[str] = None
    risk_score: Optional[int] = None  # 0-100, higher is riskier; None if unscored


def is_complaint(text: str) -> bool:
    text = text.replace("’", "'")  # curly apostrophes are common in real comments
    return bool(_COMPLAINT_RE.search(_NEGATED_SCAM_RE.sub("", text)))


def _normalize(text: str) -> str:
    """Lowercase letters and digits only, so spacing, punctuation and emoji
    don't hide a copy-pasted comment."""
    return re.sub(r"[\W_]+", "", text.lower())


def parse_comments(
    posts: list[dict[str, Any]], handle: str
) -> list[InstagramComment]:
    """Flatten each post's latestComments, skipping the store's own replies
    (it answering customers isn't evidence either way)."""
    comments = []
    for post in posts:
        for raw in post.get("latestComments") or []:
            owner = (raw.get("ownerUsername") or "").strip()
            text = (raw.get("text") or "").strip()
            if not text or owner.lower() == handle.lower():
                continue
            comments.append(
                InstagramComment(owner=owner, text=text, post_url=post.get("url"))
            )
    return comments


def analyze_comments(comments: list[InstagramComment]) -> CommentFindings:
    """Risk is the worse of two signals: how much of the discussion is
    complaints, and how much is text copy-pasted across accounts."""
    total = len(comments)
    if total < MIN_COMMENTS:
        return CommentFindings(
            analyzed=total,
            skip_reason=f"only {total} comment(s) to judge (need {MIN_COMMENTS})",
        )

    complaints = [c for c in comments if is_complaint(c.text)]
    complaint_risk = 0
    if len(complaints) >= MIN_COMPLAINTS:
        share = len(complaints) / total
        complaint_risk = round(
            COMPLAINT_MAX_RISK * min(share / COMPLAINT_SHARE_FOR_MAX_RISK, 1)
        )

    authors_by_text: dict[str, set[str]] = defaultdict(set)
    for comment in comments:
        key = _normalize(comment.text)
        if len(key) >= DUPLICATE_MIN_LENGTH:
            authors_by_text[key].add(comment.owner.lower())
    repeated = {
        key
        for key, authors in authors_by_text.items()
        if len(authors) >= DUPLICATE_MIN_AUTHORS
    }
    duplicate_comments = sum(_normalize(c.text) in repeated for c in comments)
    duplicate_risk = round(
        DUPLICATE_MAX_RISK
        * min(duplicate_comments / total / DUPLICATE_SHARE_FOR_MAX_RISK, 1)
    )

    return CommentFindings(
        analyzed=total,
        complaints=complaints,
        complaint_risk=complaint_risk,
        duplicate_comments=duplicate_comments,
        duplicate_risk=duplicate_risk,
        risk_score=max(complaint_risk, duplicate_risk),
    )
