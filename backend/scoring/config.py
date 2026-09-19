from .types import (
    CategoryScoringConfig,
    ScoringConfig,
    SourceScoringConfig,
)


SCORING_CONFIG = ScoringConfig(
    categories=(
        CategoryScoringConfig(
            id="third-party-reviews",
            label="Third-Party Reviews",
            weight=0.5,
            sources=(
                SourceScoringConfig(
                    id="reddit",
                    label="Reddit",
                    weight=1.0,
                ),
            ),
        ),
        CategoryScoringConfig(
            id="onsite-review-quality",
            label="On-Site Review Quality",
            weight=0.5,
            sources=(
                SourceScoringConfig(
                    id="gptzero",
                    label="GPTZero",
                    weight=1.0,
                ),
            ),
        ),
    ),
)
