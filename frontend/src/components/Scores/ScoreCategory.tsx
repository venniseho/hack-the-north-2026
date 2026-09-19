import type { AnalysisCategory } from '@/src/types/analysis';
import { formatDisplayPercentage, hasMeaningfulScore } from '@/src/utils/score';
import { ScoreBar } from './ScoreBar';
import { StatusBadge } from '../Shared/StatusBadge';

interface ScoreCategoryProps {
  category: AnalysisCategory;
  isExpanded: boolean;
  findingsRegionId: string;
  onToggle: () => void;
}

export function ScoreCategory({
  category,
  isExpanded,
  findingsRegionId,
  onToggle,
}: ScoreCategoryProps) {
  const showScore = hasMeaningfulScore(category.status, category.maxScore);
  const sourceCount = category.sources?.length ?? 0;
  const weightLabel = category.weight
    ? category.weight.label ??
      formatDisplayPercentage(category.weight.value, category.weight.maxValue)
    : undefined;

  return (
    <article
      className={`rounded-md border bg-white shadow-sm transition dark:bg-[#082a31] ${
        isExpanded
          ? 'border-[#007889] ring-1 ring-[#007889]/20 dark:border-teal-400 dark:ring-teal-400/20'
          : 'border-slate-200 hover:border-slate-300 dark:border-teal-700/60 dark:hover:border-teal-600'
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-controls={findingsRegionId}
        className="block w-full rounded-md p-3 text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#007889]"
      >
        <div className="flex items-start justify-between gap-2">
          <h3 className="min-w-0 text-sm font-bold leading-5 text-slate-950 dark:text-white">
            {category.label}
          </h3>
          <div className="flex shrink-0 items-center gap-3">
            <span className="text-sm font-black text-slate-950 dark:text-white">
              {showScore
                ? formatDisplayPercentage(category.riskScore, category.maxScore)
                : 'Unknown'}
            </span>
            <span
              aria-hidden="true"
              className={`h-2 w-2 border-b-2 border-r-2 border-slate-400 transition-transform dark:border-teal-200/70 ${
                isExpanded ? 'rotate-[225deg]' : 'rotate-45'
              }`}
            />
          </div>
        </div>

        <div className="mt-2">
          <ScoreBar
            score={category.riskScore}
            maxScore={category.maxScore}
            status={category.status}
            label={category.scoreLabel}
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <StatusBadge status={category.status} label={category.scoreLabel ?? category.status} />
          {weightLabel && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600 dark:bg-teal-950/70 dark:text-teal-100/70">
              Weight {weightLabel}
            </span>
          )}
          {sourceCount > 0 && (
            <span className="text-[11px] font-medium text-slate-500 dark:text-teal-100/60">
              {sourceCount} source{sourceCount === 1 ? '' : 's'}
            </span>
          )}
          {typeof category.evidenceCount === 'number' && (
            <span className="text-[11px] font-medium text-slate-500 dark:text-teal-100/60">
              {category.evidenceCount} evidence
            </span>
          )}
        </div>

        {category.description && (
          <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600 dark:text-teal-100/70">
            {category.description}
          </p>
        )}

        {sourceCount > 0 && (
          <div className="flex flex-wrap gap-1 pt-3">
            {category.sources?.map((source) => (
              <span
                key={source.id}
                className="max-w-full truncate rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700 dark:bg-teal-950/70 dark:text-teal-100"
              >
                {source.label}
              </span>
            ))}
          </div>
        )}
      </button>
    </article>
  );
}
