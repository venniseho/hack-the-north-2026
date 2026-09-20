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
            weight=0.4,
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
            weight=0.3,
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
        CategoryScoringConfig(
            id="social-proof",
            label="Social Proof",
            weight=0.3,
            sources=(
                SourceScoringConfig(
                    id="instagram-tags",
                    label="Instagram Tags",
                    weight=0.4,
                ),
                # Direct customer reports outweigh the absence of tags.
                SourceScoringConfig(
                    id="instagram-comments",
                    label="Instagram Comments",
                    weight=0.6,
                ),
            ),
        ),
    ),
)
