export type RiskStatus = 'low' | 'medium' | 'high' | 'unknown';

export type ConfidenceLevel = 'low' | 'medium' | 'high';

export type FindingSeverity = 'info' | 'warning' | 'danger' | 'positive';

export interface ScoreWeight {
  value: number;
  maxValue: number;
  label?: string;
}

export interface ScamAnalysis {
  store: {
    name?: string;
    domain: string;
  };
  product?: {
    name?: string;
    price?: string;
    imageUrl?: string;
  };
  overall: {
    riskScore: number;
    maxScore: number;
    coverage?: number;
    label?: string;
    status?: RiskStatus;
    confidence?: ConfidenceLevel;
    evidenceCount?: number;
    summary?: string;
  };
  categories: AnalysisCategory[];
  findings: Finding[];
}

export interface AnalysisCategory {
  id: string;
  label: string;
  riskScore: number;
  maxScore: number;
  scoreLabel?: string;
  status?: RiskStatus;
  description?: string;
  weight?: ScoreWeight;
  sources?: AnalysisSource[];
  evidenceCount?: number;
}

export interface AnalysisSource {
  id: string;
  label: string;
  riskScore?: number;
  maxScore?: number;
  scoreLabel?: string;
  status?: RiskStatus;
  evidenceCount?: number;
  weight?: ScoreWeight;
  metadata?: Record<string, unknown>;
}

export interface Finding {
  id: string;
  categoryId: string;
  sourceId?: string;
  title: string;
  description: string;
  severity: FindingSeverity;
  badgeLabel?: string;
  evidenceCount?: number;
  evidence?: Evidence[];
  impact?: number;
  metadata?: Record<string, unknown>;
}

export interface Evidence {
  id: string;
  label: string;
  source?: string;
  url?: string;
  excerpt?: string;
  date?: string;
  metadata?: Record<string, unknown>;
}
