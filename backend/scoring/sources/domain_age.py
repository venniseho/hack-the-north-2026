from ..types import ScoreStatus, SourceScore


def score_domain_age() -> SourceScore:
    """Return unavailable until domain-age collection and rules are defined."""
    return SourceScore(
        id="domain-age",
        label="Domain Age",
        status=ScoreStatus.UNAVAILABLE,
        risk_score=None,
        metadata={"placeholder": True},
    )
