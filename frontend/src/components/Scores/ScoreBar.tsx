import type { RiskStatus } from '@/src/types/analysis';
import { formatDisplayPercentage, getDisplayPercentage } from '@/src/utils/score';

interface ScoreBarProps {
  score: number;
  maxScore: number;
  label?: string;
  status?: RiskStatus;
  showValue?: boolean;
}

const barClasses: Record<RiskStatus, string> = {
  low: 'bg-emerald-500 dark:bg-emerald-400',
  medium: 'bg-amber-500 dark:bg-amber-400',
  high: 'bg-rose-500 dark:bg-rose-400',
  unknown: 'bg-slate-400 dark:bg-slate-500',
};

export function ScoreBar({
  score,
  maxScore,
  label,
  status = 'unknown',
  showValue = false,
}: ScoreBarProps) {
  const percentage = getDisplayPercentage(score, maxScore);

  return (
    <div className="space-y-1">
      {(label || showValue) && (
        <div className="flex items-center justify-between gap-2 text-[11px] font-semibold text-slate-600 dark:text-teal-100/70">
          {label && <span className="min-w-0 truncate">{label}</span>}
          {showValue && <span className="shrink-0">{formatDisplayPercentage(score, maxScore)}</span>}
        </div>
      )}
      <div
        className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-teal-950"
        role="meter"
        aria-label={label ?? 'Risk score'}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percentage)}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${barClasses[status]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
