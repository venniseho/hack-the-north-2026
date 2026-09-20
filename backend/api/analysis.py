from urllib.parse import urlparse

from ..scoring import SCORING_CONFIG, aggregate_overall
from ..scoring.mock_data import mock_source_scores
from ..scoring.types import (
    CategoryScore,
    CategoryScoringConfig,
    ScoringFinding,
    ScoringResult,
    SourceScore,
    SourceScoringConfig,
)
from .models import (
    AnalysisResponse,
    CategoryScoreResponse,
    ScoringFindingResponse,
    ScoringResponse,
    SourceScoreResponse,
    StoreResponse,
)


def _domain_from_url(current_url: str) -> str:
    parsed = urlparse(current_url)
    return parsed.hostname or current_url


def _finding_response(finding: ScoringFinding) -> ScoringFindingResponse:
    return ScoringFindingResponse(
        ruleId=finding.rule_id,
        title=finding.title,
        explanation=finding.explanation,
        impact=finding.impact,
        metadata=dict(finding.metadata) if finding.metadata is not None else None,
    )


def _source_response(
    config: SourceScoringConfig,
    score: SourceScore,
) -> SourceScoreResponse:
    return SourceScoreResponse(
        id=score.id,
        label=score.label,
        weight=config.weight,
        status=score.status,
        riskScore=score.risk_score,
        findings=[_finding_response(finding) for finding in score.findings],
        metadata=dict(score.metadata) if score.metadata is not None else None,
    )


def _category_response(
    config: CategoryScoringConfig,
    score: CategoryScore,
) -> CategoryScoreResponse:
    return CategoryScoreResponse(
        id=score.id,
        label=score.label,
        weight=config.weight,
        riskScore=score.risk_score,
        coverage=score.coverage,
        sources=[
            _source_response(source_config, source_score)
            for source_config, source_score in zip(config.sources, score.sources)
        ],
    )


def _scoring_response(result: ScoringResult) -> ScoringResponse:
    return ScoringResponse(
        overallRisk=result.overall_risk,
        coverage=result.coverage,
        categories=[
            _category_response(category_config, category_score)
            for category_config, category_score in zip(
                SCORING_CONFIG.categories,
                result.categories,
            )
        ],
    )


def create_analysis(
    current_url: str, reddit: SourceScore, instagram: SourceScore
) -> AnalysisResponse:
    """Build the API response from the real Reddit and Instagram scores plus
    mock scores for the sources that don't have collectors yet."""
    result = aggregate_overall(
        SCORING_CONFIG, (reddit, instagram, *mock_source_scores())
    )
    return AnalysisResponse(
        store=StoreResponse(domain=_domain_from_url(current_url)),
        scoring=_scoring_response(result),
    )
