from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, TypeAlias


RiskScore: TypeAlias = float


class ScoreStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient-data"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScoringFinding:
    rule_id: str
    title: str
    explanation: str
    impact: float | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SourceScore:
    id: str
    label: str
    status: ScoreStatus
    risk_score: RiskScore | None
    findings: tuple[ScoringFinding, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SourceScoringConfig:
    id: str
    label: str
    weight: float


@dataclass(frozen=True, slots=True)
class CategoryScoringConfig:
    id: str
    label: str
    weight: float
    sources: tuple[SourceScoringConfig, ...]


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    categories: tuple[CategoryScoringConfig, ...]


@dataclass(frozen=True, slots=True)
class CategoryScore:
    id: str
    label: str
    risk_score: RiskScore | None
    coverage: float
    sources: tuple[SourceScore, ...]


@dataclass(frozen=True, slots=True)
class ScoringResult:
    overall_risk: RiskScore | None
    coverage: float
    categories: tuple[CategoryScore, ...]
