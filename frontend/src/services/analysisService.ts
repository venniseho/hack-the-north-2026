import { requestAnalysis } from '@/lib/api';
import type {
  AnalysisCategory,
  ConfidenceLevel,
  Evidence,
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
  mode?: 'standard' | 'insufficient-data';
  /** Review text extracted from the user's tab, forwarded to GPTZero scoring. */
  reviews?: string[];
  via?: string;
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

/**
 * Severity of one finding, from its own impact where the source reports one.
 *
 * Falling back to the source's score makes every card in a source look the
 * same, which is actively misleading for GPTZero: its risk score is the *mean*
 * probability across reviews, so a store with three fabricated reviews among
 * twenty averages low and the cards quoting those three would read 'Info'. The
 * per-finding impact is that review's own probability, which is what the badge
 * should reflect. Sources with no per-finding impact (Reddit) keep the old
 * behaviour.
 */
function findingSeverity(impact: number | null | undefined, sourceRisk: number | null): FindingSeverity {
  const status = riskStatus(impact ?? sourceRisk);
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

/**
 * Turn a finding's metadata into the expandable evidence row.
 *
 * Everything a source knows about a finding already arrives in `metadata` -
 * GPTZero sends the review's own AI probability, predicted class and whether
 * the text was too short to be reliable; Reddit sends the thread URL. Without
 * this the panel shows the claim and hides the grounds for it.
 *
 * `url` is lifted out because EvidenceItem renders it as an 'Open' link rather
 * than a row in the detail table.
 */
function mapEvidence(
  findingId: string,
  source: ApiSourceScore,
  finding: ApiSourceScore['findings'][number],
): Evidence[] {
  const { url, ...details } = finding.metadata ?? {};
  const hasDetails = Object.keys(details).length > 0;
  if (!hasDetails && typeof url !== 'string') return [];

  return [
    {
      id: `${findingId}:evidence`,
      label: finding.title,
      source: source.label,
      url: typeof url === 'string' ? url : undefined,
      metadata: hasDetails ? details : undefined,
    },
  ];
}

function mapFindings(category: ApiCategoryScore, source: ApiSourceScore): Finding[] {
  return source.findings.map((finding, index) => {
    // The index is part of the id because a rule fires once per item, not once
    // per source: every flagged review is GPTZERO_AI_REVIEW and two Reddit
    // posts of the same severity share REDDIT_*. Without it these collide into
    // one React key and the list mis-reconciles - expanding one card opens
    // another.
    const id = `${category.id}:${source.id}:${finding.ruleId}:${index}`;
    const evidence = mapEvidence(id, source, finding);

    return {
      id,
      categoryId: category.id,
      sourceId: source.id,
      title: finding.title,
      description: finding.explanation,
      severity: findingSeverity(finding.impact, source.riskScore),
      evidenceCount: evidence.length,
      evidence,
      impact: finding.impact ?? undefined,
      metadata: finding.metadata ?? undefined,
    };
  });
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
      reviews: request?.reviews,
      via: request?.via,
    });
    return mapAnalysisResponse(response);
  },
};
