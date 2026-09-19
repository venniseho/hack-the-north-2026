from ..types import ScoreStatus, SourceScore


def score_onsite_reviews() -> SourceScore:
    """Return unavailable until GPTZero collection and scoring rules are defined."""
    return SourceScore(
        id="gptzero",
        label="GPTZero",
        status=ScoreStatus.UNAVAILABLE,
        risk_score=None,
        metadata={"placeholder": True},
    )
