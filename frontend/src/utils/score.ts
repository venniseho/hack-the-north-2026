import type { RiskStatus } from '@/src/types/analysis';

export function getDisplayPercentage(score: number, maxScore: number): number {
  if (maxScore <= 0) return 0;

  return Math.min(100, Math.max(0, (score / maxScore) * 100));
}

export function formatDisplayPercentage(score: number, maxScore: number): string {
  return `${Math.round(getDisplayPercentage(score, maxScore))}%`;
}

export function hasMeaningfulScore(status: RiskStatus | undefined, maxScore: number): boolean {
  return status !== 'unknown' && maxScore > 0;
}
