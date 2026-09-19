from collections.abc import Iterable

from .calculate_coverage import calculate_coverage
from .types import (
    CategoryScore,
    CategoryScoringConfig,
    ScoringConfig,
    ScoreStatus,
    SourceScore,
)
from .validate_config import validate_scoring_config, validate_source_score


def _unavailable_source(source_id: str, label: str) -> SourceScore:
    return SourceScore(
        id=source_id,
        label=label,
        status=ScoreStatus.UNAVAILABLE,
        risk_score=None,
    )


def aggregate_category(
    config: CategoryScoringConfig,
    source_scores: Iterable[SourceScore],
) -> CategoryScore:
    validate_scoring_config(ScoringConfig(categories=(config,)))

    configured_source_ids = {source.id for source in config.sources}
    source_scores_by_id: dict[str, SourceScore] = {}

    for source_score in source_scores:
        validate_source_score(source_score)

        if source_score.id not in configured_source_ids:
            raise ValueError(
                f'Source score "{source_score.id}" is not configured for '
                f'category "{config.id}".'
            )
        if source_score.id in source_scores_by_id:
            raise ValueError(f'Duplicate source score id: "{source_score.id}".')

        source_scores_by_id[source_score.id] = source_score

    sources = tuple(
        SourceScore(
            id=source_config.id,
            label=source_config.label,
            status=source_score.status,
            risk_score=source_score.risk_score,
            findings=tuple(source_score.findings),
            metadata=source_score.metadata,
        )
        if (source_score := source_scores_by_id.get(source_config.id)) is not None
        else _unavailable_source(source_config.id, source_config.label)
        for source_config in config.sources
    )

    weighted_risk = 0.0
    available_weight = 0.0

    for source_config in config.sources:
        source_score = source_scores_by_id.get(source_config.id)
        if (
            source_score is not None
            and source_score.status is ScoreStatus.AVAILABLE
            and source_config.weight > 0
        ):
            # Validation above guarantees an available score is numeric.
            weighted_risk += float(source_score.risk_score) * source_config.weight
            available_weight += source_config.weight

    coverage = calculate_coverage(
        (
            source_config.weight,
            100.0
            if (
                (source_score := source_scores_by_id.get(source_config.id))
                is not None
                and source_score.status is ScoreStatus.AVAILABLE
            )
            else 0.0,
        )
        for source_config in config.sources
    )

    return CategoryScore(
        id=config.id,
        label=config.label,
        risk_score=(
            weighted_risk / available_weight if available_weight > 0 else None
        ),
        coverage=coverage,
        sources=sources,
    )
