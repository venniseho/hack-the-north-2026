import { useEffect, useId } from 'react';
import type {
  AnalysisCategory,
  AnalysisSource,
  ScamAnalysis,
  ScoreWeight,
} from '@/src/types/analysis';
import { getDisplayPercentage } from '@/src/utils/score';

interface ScoreCalculationModalProps {
  analysis: ScamAnalysis;
  onClose: () => void;
}

interface FormulaTerm {
  label: string;
  score: number;
  weight: number;
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
}

function scorePercentage(
  riskScore: number | undefined,
  maxScore: number | undefined,
): number | null {
  if (riskScore === undefined || maxScore === undefined || maxScore <= 0) return null;
  return getDisplayPercentage(riskScore, maxScore);
}

function weightPercentage(weight: ScoreWeight | undefined): number | null {
  if (!weight || weight.maxValue <= 0) return null;
  return getDisplayPercentage(weight.value, weight.maxValue);
}

function buildFormula(terms: FormulaTerm[], result: number | null): string {
  const availableTerms = terms.filter((term) => term.weight > 0);
  const availableWeight = availableTerms.reduce((sum, term) => sum + term.weight, 0);

  if (availableTerms.length === 0 || availableWeight <= 0 || result === null) {
    return 'No available weighted scores to calculate.';
  }

  const numerator = availableTerms
    .map((term) => `${formatNumber(term.score)} × ${formatNumber(term.weight)}%`)
    .join(' + ');

  return `(${numerator}) ÷ ${formatNumber(availableWeight)}% = ${formatNumber(result)}`;
}

function categoryTerms(category: AnalysisCategory): FormulaTerm[] {
  return (category.sources ?? []).flatMap((source) => {
    const score = scorePercentage(source.riskScore, source.maxScore);
    const weight = weightPercentage(source.weight);

    return score !== null && weight !== null
      ? [{ label: source.label, score, weight }]
      : [];
  });
}

function overallTerms(analysis: ScamAnalysis): FormulaTerm[] {
  return analysis.categories.flatMap((category) => {
    const score = scorePercentage(category.riskScore, category.maxScore);
    const weight = weightPercentage(category.weight);

    return score !== null && weight !== null
      ? [{ label: category.label, score, weight }]
      : [];
  });
}

function FormulaCard({ title, formula }: { title: string; formula: string }) {
  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-teal-800/80 dark:bg-[#061f24]">
      <p className="text-[10px] font-black uppercase tracking-wide text-slate-500 dark:text-teal-100/55">
        {title}
      </p>
      <p className="mt-1 overflow-x-auto whitespace-nowrap font-mono text-[11px] font-bold text-slate-800 dark:text-teal-50">
        {formula}
      </p>
    </div>
  );
}

function RiskNode({
  kind,
  label,
  score,
  coverage,
  unavailable = false,
}: {
  kind: 'overall' | 'category' | 'source';
  label: string;
  score: number | null;
  coverage?: number;
  unavailable?: boolean;
}) {
  const nodeClasses = {
    overall:
      'border-[#007889] bg-[#007889] text-white shadow-md dark:border-teal-400 dark:bg-[#07505a]',
    category:
      'border-slate-300 bg-white text-slate-950 shadow-sm dark:border-teal-700 dark:bg-[#082a31] dark:text-white',
    source:
      'border-slate-200 bg-slate-50 text-slate-950 dark:border-teal-800 dark:bg-[#061f24] dark:text-white',
  }[kind];

  return (
    <div className={`rounded-lg border px-3 py-2.5 ${nodeClasses} ${unavailable ? 'border-dashed opacity-70' : ''}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className={`text-[9px] font-black uppercase tracking-wider ${kind === 'overall' ? 'text-teal-50/75' : 'text-slate-500 dark:text-teal-100/55'}`}>
            {kind === 'overall' ? 'Overall risk' : kind}
          </p>
          <p className="truncate text-xs font-black">{label}</p>
        </div>
        <span className="shrink-0 text-lg font-black">
          {score === null ? 'Unavailable' : `${formatNumber(score)}%`}
        </span>
      </div>
      {typeof coverage === 'number' && (
        <p className={`mt-1 text-[10px] font-semibold ${kind === 'overall' ? 'text-teal-50/80' : 'text-slate-500 dark:text-teal-100/60'}`}>
          Coverage {formatNumber(coverage)}%
        </p>
      )}
    </div>
  );
}

function TreeBranch({
  weight,
  children,
}: {
  weight: number | null;
  children: React.ReactNode;
}) {
  return (
    <div className="relative pt-10 before:absolute before:-left-5 before:top-14 before:w-5 before:border-t-2 before:border-teal-300 dark:before:border-teal-700">
      <span className="absolute -left-3 top-4 z-10 rounded-full border border-teal-200 bg-white px-1.5 py-0.5 text-[9px] font-black text-[#007889] shadow-sm dark:border-teal-700 dark:bg-[#082a31] dark:text-teal-200">
        {weight === null ? 'Weight —' : `${formatNumber(weight)}% weight`}
      </span>
      {children}
    </div>
  );
}

function SourceBranch({ source }: { source: AnalysisSource }) {
  const score = scorePercentage(source.riskScore, source.maxScore);
  const weight = weightPercentage(source.weight);

  return (
    <TreeBranch weight={weight}>
      <RiskNode
        kind="source"
        label={source.label}
        score={score}
        unavailable={score === null}
      />
    </TreeBranch>
  );
}

function CategoryBranch({ category }: { category: AnalysisCategory }) {
  const score = scorePercentage(category.riskScore, category.maxScore);
  const weight = weightPercentage(category.weight);
  const terms = categoryTerms(category);

  return (
    <TreeBranch weight={weight}>
      <RiskNode
        kind="category"
        label={category.label}
        score={score}
        coverage={
          category.sources && category.sources.length > 0
            ? terms.reduce((sum, term) => sum + term.weight, 0)
            : undefined
        }
        unavailable={score === null}
      />
      <FormulaCard
        title={`${category.label} calculation`}
        formula={buildFormula(terms, score)}
      />

      {(category.sources?.length ?? 0) > 0 && (
        <div className="ml-4 border-l-2 border-teal-200 pl-5 dark:border-teal-800">
          {category.sources?.map((source) => (
            <SourceBranch key={source.id} source={source} />
          ))}
        </div>
      )}
    </TreeBranch>
  );
}

export function ScoreCalculationModal({ analysis, onClose }: ScoreCalculationModalProps) {
  const titleId = useId();
  const overallScore = scorePercentage(
    analysis.overall.riskScore,
    analysis.overall.maxScore,
  );
  const terms = overallTerms(analysis);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/70 p-3 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[calc(100%-1.5rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-teal-700 dark:bg-[#082a31]"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-teal-800">
          <div>
            <p className="text-[10px] font-black uppercase tracking-wider text-[#007889] dark:text-teal-300">
              Transparent scoring
            </p>
            <h2 id={titleId} className="mt-0.5 text-base font-black text-slate-950 dark:text-white">
              How this score is calculated
            </h2>
          </div>
          <button
            type="button"
            autoFocus
            onClick={onClose}
            aria-label="Close score calculation"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-slate-200 text-lg font-bold text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus:ring-2 focus:ring-[#007889] dark:border-teal-700 dark:text-teal-200 dark:hover:bg-teal-950"
          >
            ×
          </button>
        </header>

        <div className="min-h-0 overflow-y-auto p-4">
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-4 text-amber-900 dark:border-amber-800/70 dark:bg-amber-950/40 dark:text-amber-100">
            Scores are deterministic heuristic risk values, not scam probabilities. Missing data is excluded and available weights are renormalized.
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-teal-800 dark:bg-[#061f24]/60">
            <RiskNode
              kind="overall"
              label="Estimated Scam Risk"
              score={overallScore}
              coverage={analysis.overall.coverage}
              unavailable={overallScore === null}
            />
            <FormulaCard
              title="Overall calculation"
              formula={buildFormula(terms, overallScore)}
            />

            <div className="ml-4 border-l-2 border-teal-200 pl-5 dark:border-teal-800">
              {analysis.categories.map((category) => (
                <CategoryBranch key={category.id} category={category} />
              ))}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-semibold text-slate-500 dark:text-teal-100/55">
            <span>Node = calculated risk score</span>
            <span>Connector = configured weight</span>
          </div>
        </div>
      </section>
    </div>
  );
}
