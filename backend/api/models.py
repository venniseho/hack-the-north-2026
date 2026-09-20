from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..scoring.types import ScoreStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AnalyzeRequest(ApiModel):
    current_url: StrictStr = Field(alias="currentUrl")

    # Verbatim review text extracted from the page by the extension's content
    # script. The backend cannot collect these itself: a headless browser
    # inherits the anti-bot wall the user's own tab walks past (measured in
    # docs/ai-review-detection.md). Absent or empty means GPTZero reports
    # insufficient data, not low risk.
    reviews: list[StrictStr] = Field(default_factory=list)

    # Which extraction path produced them, as extract-reviews.js reports it
    # ('widget:judgeme', 'json-ld', 'heuristic', ...). Weak sources get their
    # confidence capped downstream by cap_confidence().
    via: StrictStr | None = None


class ScoringFindingResponse(ApiModel):
    rule_id: str = Field(alias="ruleId")
    title: str
    explanation: str
    impact: float | None
    metadata: dict[str, Any] | None


class SourceScoreResponse(ApiModel):
    id: str
    label: str
    weight: float
    status: ScoreStatus
    risk_score: float | None = Field(alias="riskScore")
    findings: list[ScoringFindingResponse]
    metadata: dict[str, Any] | None


class CategoryScoreResponse(ApiModel):
    id: str
    label: str
    weight: float
    risk_score: float | None = Field(alias="riskScore")
    coverage: float
    sources: list[SourceScoreResponse]


class ScoringResponse(ApiModel):
    overall_risk: float | None = Field(alias="overallRisk")
    coverage: float
    categories: list[CategoryScoreResponse]


class StoreResponse(ApiModel):
    domain: str


class AnalysisResponse(ApiModel):
    store: StoreResponse
    scoring: ScoringResponse
