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
            id="site-analysis",
            label="Site Analysis",
            weight=0.5,
            sources=(
                SourceScoringConfig(
                    id="domain-age",
                    label="Domain Age",
                    weight=0.6,
                ),
                SourceScoringConfig(
                    id="gptzero",
                    label="GPTZero",
                    weight=0.4,
                ),
            ),
        ),
    ),
)
