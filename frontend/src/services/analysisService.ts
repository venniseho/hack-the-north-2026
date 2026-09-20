import { requestAnalysis } from '@/lib/api';
import type {
  AnalysisCategory,
  ConfidenceLevel,
  Finding,
  FindingSeverity,
  RiskStatus,
  ScamAnalysis,
} from '@/src/types/analysis';
import type {
  AnalysisApiResponse,
  ApiCategoryScore,
  ApiScoreStatus,
  ApiSourceScore,
} from '@/src/types/scoringApi';

export interface AnalysisRequest {
  currentUrl?: string;
  instagramLinks?: string[];
  mode?: 'standard' | 'insufficient-data';
}

export interface AnalysisService {
  getAnalysis(request?: AnalysisRequest): Promise<ScamAnalysis>;
}

function riskStatus(riskScore: number | null): RiskStatus {
  if (riskScore === null) return 'unknown';
  if (riskScore >= 67) return 'high';
  if (riskScore >= 34) return 'medium';
  return 'low';
}

function riskLabel(status: RiskStatus): string {
  switch (status) {
    case 'high':
      return 'High observed risk';
    case 'medium':
      return 'Elevated observed risk';
    case 'low':
      return 'Low observed risk';
    case 'unknown':
      return 'Not enough evidence';
  }
}

function confidenceFromCoverage(coverage: number): ConfidenceLevel {
  if (coverage >= 80) return 'high';
  if (coverage >= 50) return 'medium';
  return 'low';
}

function findingSeverity(sourceRisk: number | null): FindingSeverity {
  const status = riskStatus(sourceRisk);
  if (status === 'high') return 'danger';
  if (status === 'medium') return 'warning';
  return 'info';
}

function sourceStatusLabel(status: ApiScoreStatus, riskScore: number | null): string {
  if (status === 'available') return riskLabel(riskStatus(riskScore));
  if (status === 'insufficient-data') return 'Insufficient data';
  if (status === 'error') return 'Source error';
  return 'Unavailable';
}

function mapFindings(category: ApiCategoryScore, source: ApiSourceScore): Finding[] {
  return source.findings.map((finding) => ({
    id: `${category.id}:${source.id}:${finding.ruleId}`,
    categoryId: category.id,
    sourceId: source.id,
    title: finding.title,
    description: finding.explanation,
    severity: findingSeverity(source.riskScore),
    evidenceCount: 1,
    impact: finding.impact ?? undefined,
    metadata: finding.metadata ?? undefined,
  }));
}

function mapCategory(
  category: ApiCategoryScore,
  totalCategoryWeight: number,
): AnalysisCategory {
  const status = riskStatus(category.riskScore);
  const totalSourceWeight = category.sources.reduce((sum, source) => sum + source.weight, 0);
  const evidenceCount = category.sources.reduce(
    (sum, source) => sum + source.findings.length,
    0,
  );

  return {
    id: category.id,
    label: category.label,
    riskScore: category.riskScore ?? 0,
    maxScore: category.riskScore === null ? 0 : 100,
    scoreLabel: riskLabel(status),
    status,
    description: 'Weighted risk from the available configured sources.',
    weight: { value: category.weight, maxValue: totalCategoryWeight },
    evidenceCount,
    sources: category.sources.map((source) => ({
      id: source.id,
      label: source.label,
      riskScore: source.riskScore ?? undefined,
      maxScore: source.riskScore === null ? 0 : 100,
      scoreLabel: sourceStatusLabel(source.status, source.riskScore),
      status: riskStatus(source.riskScore),
      evidenceCount: source.findings.length,
      weight: { value: source.weight, maxValue: totalSourceWeight },
      metadata: {
        ...(source.metadata ?? {}),
        scoringStatus: source.status,
      },
    })),
  };
}

export function mapAnalysisResponse(response: AnalysisApiResponse): ScamAnalysis {
  const overallStatus = riskStatus(response.scoring.overallRisk);
  const totalCategoryWeight = response.scoring.categories.reduce(
    (sum, category) => sum + category.weight,
    0,
  );
  const categories = response.scoring.categories.map((category) =>
    mapCategory(category, totalCategoryWeight),
  );
  const findings = response.scoring.categories.flatMap((category) =>
    category.sources.flatMap((source) => mapFindings(category, source)),
  );

  return {
    store: {
      name: response.store.domain,
      domain: response.store.domain,
    },
    overall: {
      riskScore: response.scoring.overallRisk ?? 0,
      maxScore: response.scoring.overallRisk === null ? 0 : 100,
      coverage: response.scoring.coverage,
      label: riskLabel(overallStatus),
      status: overallStatus,
      confidence: confidenceFromCoverage(response.scoring.coverage),
      evidenceCount: findings.length,
      summary: `Calculated from ${Math.round(response.scoring.coverage)}% of configured scoring weight.`,
    },
    categories,
    findings,
  };
}

export const analysisService: AnalysisService = {
  async getAnalysis(request) {
    const response = await requestAnalysis({
      currentUrl: request?.currentUrl,
      instagramLinks: request?.instagramLinks,
    });
    return mapAnalysisResponse(response);
  },
};
