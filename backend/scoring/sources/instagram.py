from collections import Counter

from ...agent.tools.instagram import InstagramFindings
from ...agent.tools.instagram_comments import DUPLICATE_MIN_AUTHORS, MAX_QUOTES
from ..types import ScoreStatus, ScoringFinding, SourceScore

COMMENTS_SOURCE_ID = "instagram-comments"
COMMENTS_LABEL = "Instagram Comments"

_MAX_QUOTE_CHARS = 120
_QUOTE_COUNT = MAX_QUOTES


def _quote(text: str, limit: int = _MAX_QUOTE_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def score_instagram_comments(findings: InstagramFindings) -> SourceScore:
    """Convert the comment analysis into a source score.

    A store we couldn't judge (no link, private, too few comments) is
    INSUFFICIENT_DATA rather than a clean bill of health, matching Reddit.
    """
    comments = findings.comments
    metadata = {"handle": findings.handle, "comments_analyzed": comments.analyzed}

    error = findings.error or comments.error
    if error:
        return SourceScore(
            id=COMMENTS_SOURCE_ID,
            label=COMMENTS_LABEL,
            status=ScoreStatus.ERROR,
            risk_score=None,
            metadata={**metadata, "error": error},
        )

    if comments.risk_score is None:
        return SourceScore(
            id=COMMENTS_SOURCE_ID,
            label=COMMENTS_LABEL,
            status=ScoreStatus.INSUFFICIENT_DATA,
            risk_score=None,
            metadata={**metadata, "reason": comments.skip_reason},
        )

    handle, analyzed = findings.handle, comments.analyzed
    profile_url = f"https://www.instagram.com/{handle}/"
    found: list[ScoringFinding] = []

    if comments.complaint_risk > 0:
        complaints = comments.complaints
        # The LLM's own breakdown, with its one or two best examples quoted.
        quotes = comments.complaint_quotes or complaints[:_QUOTE_COUNT]
        explanation = comments.complaint_summary or (
            f"{len(complaints)} of {analyzed} comments on @{handle}'s posts "
            "report problems."
        )
        if quotes:
            explanation += " e.g. " + " / ".join(
                f"“{_quote(c.text)}”" for c in quotes
            )
        found.append(
            ScoringFinding(
                rule_id="INSTAGRAM_COMPLAINT_COMMENTS",
                title="Customers are complaining in the comments",
                explanation=explanation,
                impact=float(comments.complaint_risk),
                metadata={
                    "url": profile_url,
                    "handle": handle,
                    "complaints": len(complaints),
                    "comments_analyzed": analyzed,
                    "categories": dict(Counter(c.category for c in complaints)),
                    "samples": [
                        {"text": _quote(c.text, 300), "post_url": c.post_url}
                        for c in quotes
                    ],
                },
            )
        )

    if comments.duplicate_risk > 0:
        found.append(
            ScoringFinding(
                rule_id="INSTAGRAM_DUPLICATE_COMMENTS",
                title="Identical comments from multiple accounts",
                explanation=(
                    f"{comments.duplicate_comments} of {analyzed} comments on "
                    f"@{handle}'s posts repeat text posted by "
                    f"{DUPLICATE_MIN_AUTHORS}+ different accounts, which can "
                    "indicate manufactured engagement."
                ),
                impact=float(comments.duplicate_risk),
                metadata={
                    "url": profile_url,
                    "handle": handle,
                    "duplicate_comments": comments.duplicate_comments,
                    "comments_analyzed": analyzed,
                },
            )
        )

    if not found:
        found.append(
            ScoringFinding(
                rule_id="INSTAGRAM_CLEAN_COMMENTS",
                title="Comments look organic",
                explanation=(
                    f"No pattern of complaints or copy-pasted comments across "
                    f"{analyzed} comments on @{handle}'s posts."
                ),
                impact=0.0,
                metadata={"url": profile_url, "handle": handle},
            )
        )

    return SourceScore(
        id=COMMENTS_SOURCE_ID,
        label=COMMENTS_LABEL,
        status=ScoreStatus.AVAILABLE,
        risk_score=float(comments.risk_score),
        findings=tuple(found),
        metadata=metadata,
    )
