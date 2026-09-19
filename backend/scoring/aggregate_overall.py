from collections.abc import Iterable

from .aggregate_category import aggregate_category
from .calculate_coverage import calculate_coverage
from .types import ScoringConfig, ScoringResult, SourceScore
from .validate_config import validate_scoring_config, validate_source_score


def aggregate_overall(
    config: ScoringConfig,
    source_scores: Iterable[SourceScore],
) -> ScoringResult:
    validate_scoring_config(config)

    configured_source_ids = {
        source.id
        for category in config.categories
        for source in category.sources
    }
    source_scores_by_id: dict[str, SourceScore] = {}

    for source_score in source_scores:
        validate_source_score(source_score)

        if source_score.id not in configured_source_ids:
            raise ValueError(
                f'Source score "{source_score.id}" is not present in the configuration.'
            )
        if source_score.id in source_scores_by_id:
            raise ValueError(f'Duplicate source score id: "{source_score.id}".')

        source_scores_by_id[source_score.id] = source_score

    categories = tuple(
        aggregate_category(
            category_config,
            (
                source_scores_by_id[source_config.id]
                for source_config in category_config.sources
                if source_config.id in source_scores_by_id
            ),
        )
        for category_config in config.categories
    )

    weighted_risk = 0.0
    available_weight = 0.0

    for category_config, category_score in zip(config.categories, categories):
        if category_score.risk_score is not None and category_config.weight > 0:
            weighted_risk += category_score.risk_score * category_config.weight
            available_weight += category_config.weight

    return ScoringResult(
        overall_risk=(
            weighted_risk / available_weight if available_weight > 0 else None
        ),
        coverage=calculate_coverage(
            (category_config.weight, category_score.coverage)
            for category_config, category_score in zip(config.categories, categories)
        ),
        categories=categories,
    )
