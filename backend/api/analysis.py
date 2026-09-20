import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from ..agent.tools.product_reviews import score_reviews
from ..scoring import SCORING_CONFIG, aggregate_overall
from ..scoring.mock_data import mock_source_scores
from ..scoring.sources.gptzero import no_score, score_onsite_reviews
from ..scoring.types import (
    CategoryScore,
    CategoryScoringConfig,
    ScoreStatus,
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


# Explicit rather than relying on agent.agent calling this at import time: if
# that import ever moves, GPTZERO_API_KEY would silently go missing and GPTZero
# would report UNAVAILABLE on every request.
load_dotenv()


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


async def analyze_reviews(reviews: list[str], via: str | None) -> SourceScore:
    """Score the reviews the extension extracted, or say why we couldn't.

    The caller supplies the review text because only the user's own tab can see
    it; see the note on `AnalyzeRequest.reviews`.
    """
    if not reviews:
        return no_score(
            ScoreStatus.INSUFFICIENT_DATA,
            "no reviews were extracted from this page",
        )

    api_key = os.environ.get("GPTZERO_API_KEY", "")
    if not api_key:
        # A deployment problem, not a fact about the store - so UNAVAILABLE,
        # which drops gptzero's weight out of coverage rather than counting it
        # as a source that looked and found nothing.
        return no_score(ScoreStatus.UNAVAILABLE, "GPTZERO_API_KEY is not configured")

    verdict, prepared = await score_reviews(reviews, api_key=api_key, via=via)
    return score_onsite_reviews(verdict, prepared)


def create_analysis(
    current_url: str,
    reddit: SourceScore,
    gptzero: SourceScore,
) -> AnalysisResponse:
    """Build the API response from the real Reddit and GPTZero scores, plus
    mock scores for the sources that don't have collectors yet."""
    result = aggregate_overall(
        SCORING_CONFIG,
        (reddit, gptzero, *mock_source_scores()),
    )
    return AnalysisResponse(
        store=StoreResponse(domain=_domain_from_url(current_url)),
        scoring=_scoring_response(result),
    )
