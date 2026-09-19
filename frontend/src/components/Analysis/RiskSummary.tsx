import type { AnalysisCategory, Finding } from '@/src/types/analysis';
import { CategoryGrid } from '../Scores/CategoryGrid';

interface RiskSummaryProps {
  categories: AnalysisCategory[];
  findings: Finding[];
}

export function RiskSummary({ categories, findings }: RiskSummaryProps) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-black text-slate-950 dark:text-white">Score Breakdown</h2>
        <span className="text-[11px] font-semibold text-slate-500 dark:text-teal-100/60">
          {categories.length} checked
        </span>
      </div>
      <CategoryGrid categories={categories} findings={findings} />
    </section>
  );
}
