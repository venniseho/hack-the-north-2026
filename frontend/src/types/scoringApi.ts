export type ApiScoreStatus =
  | 'available'
  | 'unavailable'
  | 'insufficient-data'
  | 'error';

export interface ApiScoringFinding {
  ruleId: string;
  title: string;
  explanation: string;
  impact: number | null;
  metadata: Record<string, unknown> | null;
}

export interface ApiSourceScore {
  id: string;
  label: string;
  weight: number;
  status: ApiScoreStatus;
  riskScore: number | null;
  findings: ApiScoringFinding[];
  metadata: Record<string, unknown> | null;
}

export interface ApiCategoryScore {
  id: string;
  label: string;
  weight: number;
  riskScore: number | null;
  coverage: number;
  sources: ApiSourceScore[];
}

export interface AnalysisApiResponse {
  store: {
    domain: string;
  };
  scoring: {
    overallRisk: number | null;
    coverage: number;
    categories: ApiCategoryScore[];
  };
}
