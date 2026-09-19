from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..scoring.types import ScoreStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AnalyzeRequest(ApiModel):
    current_url: StrictStr | None = Field(default=None, alias="currentUrl")


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
