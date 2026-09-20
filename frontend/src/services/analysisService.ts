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
  instagramLinks?: string[];
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

const redditSeverityPresentation = {
  critical: { severity: 'danger', badgeLabel: 'Critical' },
  major: { severity: 'danger', badgeLabel: 'Major' },
  moderate: { severity: 'warning', badgeLabel: 'Moderate' },
  minor: { severity: 'info', badgeLabel: 'Minor' },
  positive: { severity: 'positive', badgeLabel: 'Positive' },
} as const satisfies Record<string, { severity: FindingSeverity; badgeLabel: string }>;

/** Preserve the per-post severity assigned by the Reddit researcher. */
function redditPresentation(
  source: ApiSourceScore,
  finding: ApiSourceScore['findings'][number],
): { severity: FindingSeverity; badgeLabel?: string } | undefined {
  if (source.id !== 'reddit') return undefined;

  const severity = finding.metadata?.severity;
  if (typeof severity !== 'string' || !(severity in redditSeverityPresentation)) {
    return undefined;
  }

  return redditSeverityPresentation[severity as keyof typeof redditSeverityPresentation];
}

function sourceStatusLabel(status: ApiScoreStatus, riskScore: number | null): string {
  if (status === 'available') return riskLabel(riskStatus(riskScore));
  if (status === 'insufficient-data') return 'Insufficient data';
  if (status === 'error') return 'Source error';
  return 'Unavailable';
}

function sourceUrl(metadata: Record<string, unknown> | null): string | undefined {
  const value = metadata?.url;
  if (typeof value !== 'string') return undefined;

  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function mapEvidence(
  findingId: string,
  source: ApiSourceScore,
  finding: ApiSourceScore['findings'][number],
): Evidence[] {
  const metadata = { ...(finding.metadata ?? {}) };
  delete metadata.url;
  const url = sourceUrl(finding.metadata);
  const hasDetails = Object.keys(metadata).length > 0;

  if (!hasDetails && !url) return [];

  return [
    {
      id: `${findingId}:evidence`,
      label: finding.title,
      source: source.label,
      url,
      excerpt: finding.explanation,
      metadata: hasDetails ? metadata : undefined,
    },
  ];
}

function mapFindings(category: ApiCategoryScore, source: ApiSourceScore): Finding[] {
  return source.findings.map((finding, index) => {
    // Rules can fire once per item, so repeated rule IDs still need unique keys.
    const id = `${category.id}:${source.id}:${finding.ruleId}:${index}`;
    const evidence = mapEvidence(id, source, finding);
    const presentation = redditPresentation(source, finding);

    return {
      id,
      categoryId: category.id,
      sourceId: source.id,
      title: finding.title,
      description: finding.explanation,
      severity:
        presentation?.severity ?? findingSeverity(finding.impact, source.riskScore),
      badgeLabel: presentation?.badgeLabel,
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
      instagramLinks: request?.instagramLinks,
      reviews: request?.reviews,
      via: request?.via,
    });
    return mapAnalysisResponse(response);
  },
};
