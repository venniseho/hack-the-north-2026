import math
import unittest

from backend.scoring import (
    SCORING_CONFIG,
    CategoryScoringConfig,
    ScoreStatus,
    ScoringConfig,
    ScoringFinding,
    SourceScore,
    SourceScoringConfig,
    aggregate_category,
    aggregate_overall,
    validate_scoring_config,
)


TWO_SOURCE_MVP_CONFIG = ScoringConfig(
    categories=(
        CategoryScoringConfig(
            id="third-party-reviews",
            label="Third-Party Reviews",
            weight=0.5,
            sources=(
                SourceScoringConfig(id="reddit", label="Reddit", weight=1.0),
            ),
        ),
        CategoryScoringConfig(
            id="onsite-review-quality",
            label="On-Site Review Quality",
            weight=0.5,
            sources=(
                SourceScoringConfig(id="gptzero", label="GPTZero", weight=1.0),
            ),
        ),
    )
)


def source_score(
    source_id: str,
    risk_score: float | None,
    status: ScoreStatus | None = None,
    findings: tuple[ScoringFinding, ...] = (),
) -> SourceScore:
    return SourceScore(
        id=source_id,
        label=source_id,
        status=status
        or (
            ScoreStatus.UNAVAILABLE
            if risk_score is None
            else ScoreStatus.AVAILABLE
        ),
        risk_score=risk_score,
        findings=findings,
    )


FUTURE_THIRD_PARTY_CONFIG = CategoryScoringConfig(
    id="third-party-reviews",
    label="Third-Party Reviews",
    weight=1.0,
    sources=(
        SourceScoringConfig(id="reddit", label="Reddit", weight=60.0),
        SourceScoringConfig(id="trustpilot", label="Trustpilot", weight=40.0),
    ),
)


class ScoringTests(unittest.TestCase):
    def test_case_1_averages_both_available_sources(self) -> None:
        result = aggregate_overall(
            TWO_SOURCE_MVP_CONFIG,
            (source_score("reddit", 80), source_score("gptzero", 60)),
        )

        self.assertEqual(result.overall_risk, 70)
        self.assertEqual(result.coverage, 100)

    def test_case_2_excludes_missing_reddit(self) -> None:
        result = aggregate_overall(
            TWO_SOURCE_MVP_CONFIG,
            (source_score("gptzero", 60),),
        )

        self.assertEqual(result.overall_risk, 60)
        self.assertEqual(result.coverage, 50)
        self.assertEqual(
            result.categories[0].sources[0].status,
            ScoreStatus.UNAVAILABLE,
        )

    def test_case_3_excludes_unavailable_gptzero(self) -> None:
        result = aggregate_overall(
            TWO_SOURCE_MVP_CONFIG,
            (
                source_score("reddit", 80),
                source_score("gptzero", None),
            ),
        )

        self.assertEqual(result.overall_risk, 80)
        self.assertEqual(result.coverage, 50)

    def test_case_4_returns_no_risk_when_both_are_unavailable(self) -> None:
        result = aggregate_overall(
            TWO_SOURCE_MVP_CONFIG,
            (
                source_score("reddit", None),
                source_score("gptzero", None),
            ),
        )

        self.assertIsNone(result.overall_risk)
        self.assertEqual(result.coverage, 0)

    def test_case_5_normalizes_multiple_source_weights(self) -> None:
        result = aggregate_category(
            FUTURE_THIRD_PARTY_CONFIG,
            (
                source_score("reddit", 80),
                source_score("trustpilot", 40),
            ),
        )

        self.assertEqual(result.risk_score, 64)
        self.assertEqual(result.coverage, 100)

    def test_case_6_renormalizes_when_trustpilot_is_unavailable(self) -> None:
        result = aggregate_category(
            FUTURE_THIRD_PARTY_CONFIG,
            (
                source_score("reddit", 80),
                source_score("trustpilot", None),
            ),
        )

        self.assertEqual(result.risk_score, 80)
        self.assertEqual(result.coverage, 60)

    def test_preserves_findings(self) -> None:
        finding = ScoringFinding(
            rule_id="REDDIT_MULTIPLE_NEGATIVE_THREADS",
            title="Multiple negative discussions found",
            explanation=(
                "Four independent threads contained complaints about the seller."
            ),
        )
        result = aggregate_overall(
            SCORING_CONFIG,
            (
                source_score("reddit", 80, findings=(finding,)),
                source_score("gptzero", None),
            ),
        )

        self.assertEqual(result.categories[0].sources[0].findings, (finding,))

    def test_validates_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one category"):
            validate_scoring_config(ScoringConfig(categories=()))

        no_sources = ScoringConfig(
            categories=(
                CategoryScoringConfig(
                    id="empty",
                    label="Empty",
                    weight=1,
                    sources=(),
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "at least one source"):
            validate_scoring_config(no_sources)

        negative_weight = ScoringConfig(
            categories=(
                CategoryScoringConfig(
                    id="category",
                    label="Category",
                    weight=-1,
                    sources=(
                        SourceScoringConfig(
                            id="source",
                            label="Source",
                            weight=1,
                        ),
                    ),
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "greater than or equal to 0"):
            validate_scoring_config(negative_weight)

        duplicate_sources = ScoringConfig(
            categories=(
                CategoryScoringConfig(
                    id="one",
                    label="One",
                    weight=1,
                    sources=(
                        SourceScoringConfig(
                            id="duplicate",
                            label="Duplicate",
                            weight=1,
                        ),
                    ),
                ),
                CategoryScoringConfig(
                    id="two",
                    label="Two",
                    weight=1,
                    sources=(
                        SourceScoringConfig(
                            id="duplicate",
                            label="Duplicate",
                            weight=1,
                        ),
                    ),
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "Duplicate source id"):
            validate_scoring_config(duplicate_sources)

    def test_validates_scores_and_handles_zero_weights(self) -> None:
        with self.assertRaisesRegex(ValueError, "from 0 to 100"):
            aggregate_overall(
                TWO_SOURCE_MVP_CONFIG,
                (source_score("reddit", 101),),
            )

        with self.assertRaisesRegex(ValueError, "finite number"):
            aggregate_overall(
                TWO_SOURCE_MVP_CONFIG,
                (source_score("reddit", math.nan),),
            )

        zero_weight_config = ScoringConfig(
            categories=(
                CategoryScoringConfig(
                    id="zero",
                    label="Zero",
                    weight=0,
                    sources=(
                        SourceScoringConfig(
                            id="zero-source",
                            label="Zero Source",
                            weight=0,
                        ),
                    ),
                ),
            )
        )
        result = aggregate_overall(
            zero_weight_config,
            (source_score("zero-source", 50),),
        )

        self.assertIsNone(result.overall_risk)
        self.assertEqual(result.coverage, 0)
        self.assertIsNone(result.categories[0].risk_score)


if __name__ == "__main__":
    unittest.main()
