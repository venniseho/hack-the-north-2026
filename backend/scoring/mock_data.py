"""Deterministic scores for sources that have no real collector yet.

Reddit and GPTZero have real collectors and are passed into `create_analysis`
directly - adding either here would shadow the real score with a constant.
"""

from .types import ScoringFinding, ScoreStatus, SourceScore


def mock_source_scores() -> tuple[SourceScore, ...]:
    return (
        SourceScore(
            id="domain-age",
            label="Domain Age",
            status=ScoreStatus.AVAILABLE,
            risk_score=50.0,
            findings=(
                ScoringFinding(
                    rule_id="MOCK_RECENT_DOMAIN",
                    title="Mock domain-age signal",
                    explanation=(
                        "Integration data assumes the store domain is relatively new."
                    ),
                    impact=50.0,
                    metadata={"mock": True},
                ),
            ),
            metadata={"mock": True},
        ),
    )
