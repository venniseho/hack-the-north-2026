import type { ScamAnalysis } from '@/src/types/analysis';
import { formatDisplayPercentage, hasMeaningfulScore } from '@/src/utils/score';
import { ConfidenceBadge } from '../Scores/ConfidenceBadge';
import { ScoreBar } from '../Scores/ScoreBar';
import { StatusBadge } from '../Shared/StatusBadge';

interface OverallRiskProps {
  analysis: ScamAnalysis;
}

export function OverallRisk({ analysis }: OverallRiskProps) {
  const { overall } = analysis;
  const showScore = hasMeaningfulScore(overall.status, overall.maxScore);

  return (
    <section className="rounded-md border border-slate-200 bg-white p-4 shadow-sm dark:border-teal-700/60 dark:bg-[#082a31]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-teal-100/60">
            Estimated Scam Risk
          </p>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-4xl font-black leading-none text-slate-950 dark:text-white">
              {showScore ? formatDisplayPercentage(overall.riskScore, overall.maxScore) : 'Unknown'}
            </span>
            {overall.label && <StatusBadge status={overall.status} label={overall.label} />}
          </div>
        </div>

        <ConfidenceBadge confidence={overall.confidence} />
      </div>

      <div className="mt-4">
        <ScoreBar
          score={overall.riskScore}
          maxScore={overall.maxScore}
          status={overall.status}
          showValue={false}
          label={showScore ? overall.label : 'Insufficient data'}
        />
      </div>

      {overall.summary && (
        <p className="mt-3 text-xs leading-5 text-slate-700 dark:text-teal-50/80">
          {overall.summary}
        </p>
      )}

      <p className="mt-2 text-[11px] leading-4 text-slate-500 dark:text-teal-100/55">
        Based on signals detected by our analysis. This is an estimate, not a guarantee.
      </p>
    </section>
  );
}
