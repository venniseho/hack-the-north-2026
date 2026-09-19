import { useState } from 'react';
import type { ScamAnalysis } from '@/src/types/analysis';
import { CategoryGrid } from '../Scores/CategoryGrid';
import { ScoreCalculationModal } from './ScoreCalculationModal';

interface RiskSummaryProps {
  analysis: ScamAnalysis;
}

export function RiskSummary({ analysis }: RiskSummaryProps) {
  const [showCalculation, setShowCalculation] = useState(false);

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-black text-slate-950 dark:text-white">Score Breakdown</h2>
        <div className="flex items-center gap-2">
          <span className="hidden text-[11px] font-semibold text-slate-500 sm:inline dark:text-teal-100/60">
            {analysis.categories.length} checked
          </span>
          <button
            type="button"
            onClick={() => setShowCalculation(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#007889] bg-white px-2.5 py-1.5 text-[11px] font-black text-[#007889] shadow-sm transition hover:bg-teal-50 focus:outline-none focus:ring-2 focus:ring-[#007889] focus:ring-offset-2 dark:bg-[#082a31] dark:text-teal-200 dark:hover:bg-teal-950 dark:focus:ring-offset-[#061f24]"
          >
            <svg aria-hidden="true" viewBox="0 0 20 20" className="h-3.5 w-3.5 fill-none stroke-current" strokeWidth="1.8">
              <path d="M10 3v4m0 0H5v3m5-3h5v3M5 13v4m10-4v4" />
              <circle cx="10" cy="2.5" r="1.5" />
              <circle cx="5" cy="11.5" r="1.5" />
              <circle cx="15" cy="11.5" r="1.5" />
            </svg>
            View calculation
          </button>
        </div>
      </div>
      <CategoryGrid categories={analysis.categories} findings={analysis.findings} />

      {showCalculation && (
        <ScoreCalculationModal
          analysis={analysis}
          onClose={() => setShowCalculation(false)}
        />
      )}
    </section>
  );
}
