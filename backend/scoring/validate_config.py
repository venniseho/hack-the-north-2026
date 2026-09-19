import math
from numbers import Real

from .types import ScoringConfig, ScoreStatus, SourceScore


def _validate_identifier(identifier: str, context: str) -> None:
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError(f"{context} must have a non-empty id.")


def _validate_number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{context} must be a finite number.")

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{context} must be a finite number.")

    return numeric_value


def _validate_weight(weight: object, context: str) -> None:
    if _validate_number(weight, f'{context} weight') < 0:
        raise ValueError(f'{context} weight must be greater than or equal to 0.')


def validate_scoring_config(config: ScoringConfig) -> None:
    if not config.categories:
        raise ValueError("Scoring configuration must contain at least one category.")

    category_ids: set[str] = set()
    source_ids: set[str] = set()

    for category in config.categories:
        _validate_identifier(category.id, "Category")
        _validate_weight(category.weight, f'Category "{category.id}"')

        if category.id in category_ids:
            raise ValueError(f'Duplicate category id: "{category.id}".')
        category_ids.add(category.id)

        if not category.sources:
            raise ValueError(
                f'Category "{category.id}" must contain at least one source.'
            )

        for source in category.sources:
            _validate_identifier(source.id, f'Source in category "{category.id}"')
            _validate_weight(source.weight, f'Source "{source.id}"')

            if source.id in source_ids:
                raise ValueError(f'Duplicate source id: "{source.id}".')
            source_ids.add(source.id)


def validate_source_score(source_score: SourceScore) -> None:
    _validate_identifier(source_score.id, "Source score")

    try:
        status = ScoreStatus(source_score.status)
    except ValueError as error:
        raise ValueError(
            f'Source "{source_score.id}" has an invalid status.'
        ) from error

    if status is ScoreStatus.AVAILABLE:
        if source_score.risk_score is None:
            raise ValueError(
                f'Available source "{source_score.id}" must have a risk score.'
            )

        risk_score = _validate_number(
            source_score.risk_score,
            f'Risk score for source "{source_score.id}"',
        )
        if not 0 <= risk_score <= 100:
            raise ValueError(
                f'Available source "{source_score.id}" must have a risk score '
                "from 0 to 100."
            )
        return

    if source_score.risk_score is not None:
        raise ValueError(
            f'Unavailable source "{source_score.id}" must have a null risk score.'
        )
