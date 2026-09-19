import { useId, useState } from 'react';
import type { Finding, FindingSeverity } from '@/src/types/analysis';
import { EvidenceList } from './EvidenceList';

interface FindingCardProps {
  finding: Finding;
}

const severityClasses: Record<FindingSeverity, string> = {
  info: 'border-slate-300 bg-slate-100 text-slate-700 dark:border-teal-700 dark:bg-teal-950/70 dark:text-teal-100',
  warning:
    'border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-700 dark:bg-amber-950/70 dark:text-amber-100',
  danger:
    'border-rose-300 bg-rose-100 text-rose-900 dark:border-rose-700 dark:bg-rose-950/70 dark:text-rose-100',
};

const severityLabels: Record<FindingSeverity, string> = {
  info: 'Info',
  warning: 'Warning',
  danger: 'High concern',
};

export function FindingCard({ finding }: FindingCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const evidenceRegionId = useId();
  const evidence = finding.evidence ?? [];
  const hasEvidence = evidence.length > 0;

  return (
    <article className="rounded-md border border-slate-200 bg-white p-3 shadow-sm dark:border-teal-700/60 dark:bg-[#082a31]">
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide ${severityClasses[finding.severity]}`}
        >
          {severityLabels[finding.severity]}
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-bold leading-5 text-slate-950 dark:text-white">
            {finding.title}
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-teal-100/70">
            {finding.description}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {typeof finding.evidenceCount === 'number' && (
              <span className="text-[11px] font-semibold text-slate-500 dark:text-teal-100/60">
                {finding.evidenceCount} evidence
              </span>
            )}

            {hasEvidence && (
              <button
                type="button"
                aria-expanded={isExpanded}
                aria-controls={evidenceRegionId}
                onClick={() => setIsExpanded((current) => !current)}
                className="rounded-sm text-[11px] font-black text-[#007889] underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-[#007889] dark:text-teal-200"
              >
                {isExpanded ? 'Hide evidence' : 'View evidence'}
              </button>
            )}
          </div>
        </div>
      </div>

      {hasEvidence && isExpanded && (
        <div id={evidenceRegionId}>
          <EvidenceList evidence={evidence} />
        </div>
      )}
    </article>
  );
}
