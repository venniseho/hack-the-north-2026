from ..types import ScoreStatus, SourceScore


def score_reddit() -> SourceScore:
    """Return unavailable until Reddit collection and scoring rules are defined."""
    return SourceScore(
        id="reddit",
        label="Reddit",
        status=ScoreStatus.UNAVAILABLE,
        risk_score=None,
        metadata={"placeholder": True},
    )
