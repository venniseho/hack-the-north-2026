"""Deterministic source scores used only for end-to-end integration testing."""

from .types import ScoringFinding, ScoreStatus, SourceScore


def mock_source_scores() -> tuple[SourceScore, ...]:
    return (
        SourceScore(
            id="reddit",
            label="Reddit",
            status=ScoreStatus.AVAILABLE,
            risk_score=80.0,
            findings=(
                ScoringFinding(
                    rule_id="MOCK_REDDIT_NEGATIVE_DISCUSSIONS",
                    title="Mock negative discussion signal",
                    explanation=(
                        "Integration data assumes multiple independent Reddit "
                        "complaints about the seller."
                    ),
                    impact=80.0,
                    metadata={"mock": True},
                ),
            ),
            metadata={"mock": True},
        ),
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
        SourceScore(
            id="gptzero",
            label="GPTZero",
            status=ScoreStatus.AVAILABLE,
            risk_score=70.0,
            findings=(
                ScoringFinding(
                    rule_id="MOCK_AI_REVIEW_PATTERN",
                    title="Mock AI-written review signal",
                    explanation=(
                        "Integration data assumes on-site reviews contain strong "
                        "AI-like writing patterns."
                    ),
                    impact=70.0,
                    metadata={"mock": True},
                ),
            ),
            metadata={"mock": True},
        ),
    )
