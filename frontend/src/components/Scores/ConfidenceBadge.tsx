import type { ConfidenceLevel } from '@/src/types/analysis';

interface ConfidenceBadgeProps {
  confidence?: ConfidenceLevel;
}

const confidenceClasses: Record<ConfidenceLevel, string> = {
  low: 'border-slate-300 text-slate-700 dark:border-teal-700 dark:text-teal-100',
  medium: 'border-[#007889] text-[#026876] dark:border-teal-400 dark:text-teal-100',
  high: 'border-emerald-500 text-emerald-700 dark:border-emerald-400 dark:text-emerald-100',
};

export function ConfidenceBadge({ confidence = 'low' }: ConfidenceBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${confidenceClasses[confidence]}`}
    >
      Confidence: {confidence}
    </span>
  );
}
