import type { RiskStatus } from '@/src/types/analysis';

interface StatusBadgeProps {
  status?: RiskStatus;
  label?: string;
}

const statusClasses: Record<RiskStatus, string> = {
  low: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-700/70 dark:bg-emerald-950/70 dark:text-emerald-200',
  medium:
    'border-amber-200 bg-amber-50 text-amber-800 dark:border-[#8F5B36] dark:bg-[#35271E] dark:text-[#F0BE8B]',
  high: 'border-rose-200 bg-rose-50 text-rose-800 dark:border-[#985057] dark:bg-[#352226] dark:text-[#F0A9AC]',
  unknown:
    'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300',
};

export function StatusBadge({ status = 'unknown', label }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold leading-4 ${statusClasses[status]}`}
    >
      <span className="truncate">{label ?? status}</span>
    </span>
  );
}
