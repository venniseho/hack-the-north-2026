from collections.abc import Iterable


def calculate_coverage(items: Iterable[tuple[float, float]]) -> float:
    """Return 0-100 weighted coverage from (weight, coverage) pairs."""
    weighted_items = tuple(items)
    total_weight = sum(weight for weight, _ in weighted_items)

    if total_weight == 0:
        return 0.0

    covered_weight = sum(
        weight * (coverage / 100.0) for weight, coverage in weighted_items
    )
    return covered_weight / total_weight * 100.0
