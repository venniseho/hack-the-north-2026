"""Collapse a GPTZero corpus verdict into one 0-100 risk number.

The single number is the mean `completely_generated_prob` over every review
that scored without error, rescaled to the 0-100 the rest of the scoring
pipeline uses. Reviews that errored are excluded rather than counted as 0 - a
transport failure is not evidence the review was human.
"""

from ...agent.tools.product_reviews import PreparedReviews
from ...services.gptzero import CorpusVerdict
from ..types import ScoreStatus, ScoringFinding, SourceScore

# Below this many usable reviews, the mean is one or two documents wide and a
# single false positive swings it 30+ points. Mirrors `_confidence()` in
# services.gptzero, which calls the same count 'insufficient'.
MIN_USABLE_REVIEWS = 3

# How many flagged reviews to surface as findings in the side panel.
MAX_FINDINGS = 5

# Chars of review text quoted in a finding.
QUOTE_CHARS = 160


def mean_ai_risk(verdict: CorpusVerdict) -> float:
    """The single number: mean AI probability across scored reviews, 0-100."""
    return round(verdict.mean_prob * 100.0, 1)


def no_score(status: ScoreStatus, reason: str) -> SourceScore:
    """A GPTZero score with no number, and the reason there isn't one.

    Used when scoring never ran at all: the request carried no reviews (the
    extension has no content script on this page), or the API key is missing.
    Distinct from a low risk score - we learned nothing, rather than learning
    the reviews look human.
    """
    return SourceScore(
        id="gptzero",
        label="GPTZero",
        status=status,
        risk_score=None,
        metadata={"reason": reason},
    )


def _findings(verdict: CorpusVerdict) -> tuple[ScoringFinding, ...]:
    flagged = [s for s in verdict.scores if s.error is None and s.is_ai]
    return tuple(
        ScoringFinding(
            rule_id="GPTZERO_AI_REVIEW",
            title="Review reads as AI-generated",
            explanation=score.text[:QUOTE_CHARS],
            impact=round(score.ai_prob * 100.0, 1),
            metadata={
                "aiProbability": round(score.ai_prob, 4),
                "predictedClass": score.predicted_class,
                "apiConfidence": score.confidence,
                "shortText": score.is_short,
            },
        )
        for score in flagged[:MAX_FINDINGS]
    )


def score_onsite_reviews(
    verdict: CorpusVerdict,
    prepared: PreparedReviews | None = None,
) -> SourceScore:
    """Convert a GPTZero corpus verdict into a source score.

    `prepared` is the extraction audit from `product_reviews.prepare()`; pass it
    so the panel can distinguish "this store has 2 reviews" from "this store had
    40, 38 of them duplicates".
    """
    metadata: dict[str, object] = {
        "total": verdict.total,
        "scored": verdict.scored,
        "flagged": verdict.flagged,
        "aiShare": verdict.ai_share,
        "meanProbability": verdict.mean_prob,
        "shortFlagged": verdict.short_flagged,
        "verdict": verdict.verdict,
        "confidence": verdict.confidence,
    }
    if prepared is not None:
        metadata["extraction"] = {
            "received": prepared.received,
            "usable": prepared.usable,
            "droppedShort": prepared.dropped_short,
            "droppedLong": prepared.dropped_long,
            "droppedDuplicate": prepared.dropped_duplicate,
            "droppedToCap": prepared.dropped_to_cap,
        }

    if verdict.scored < MIN_USABLE_REVIEWS:
        # Too thin to average. Not a clean bill of health - unknown.
        return SourceScore(
            id="gptzero",
            label="GPTZero",
            status=ScoreStatus.INSUFFICIENT_DATA,
            risk_score=None,
            metadata=metadata,
        )

    return SourceScore(
        id="gptzero",
        label="GPTZero",
        status=ScoreStatus.AVAILABLE,
        risk_score=mean_ai_risk(verdict),
        findings=_findings(verdict),
        metadata=metadata,
    )
