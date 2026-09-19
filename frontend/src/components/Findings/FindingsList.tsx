import type { AnalysisCategory, AnalysisSource, Finding } from '@/src/types/analysis';
import { formatDisplayPercentage } from '@/src/utils/score';
import { EmptyState } from '../Shared/EmptyState';
import { FindingCard } from './FindingCard';

interface FindingsListProps {
  categories: AnalysisCategory[];
  findings: Finding[];
  embedded?: boolean;
}

interface SourceGroup {
  source?: AnalysisSource;
  findings: Finding[];
}

function sourceSummary(source: AnalysisSource | undefined): string | undefined {
  if (!source) return undefined;

  const details = [source.scoreLabel];
  if (typeof source.riskScore === 'number' && typeof source.maxScore === 'number') {
    details.push(`Risk ${formatDisplayPercentage(source.riskScore, source.maxScore)}`);
  }
  if (source.weight) {
    details.push(`Weight ${formatDisplayPercentage(source.weight.value, source.weight.maxValue)}`);
  }

  return details.filter(Boolean).join(' · ');
}

function groupFindingsBySource(
  category: AnalysisCategory,
  findings: Finding[],
): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();

  findings.forEach((finding) => {
    const source = category.sources?.find((item) => item.id === finding.sourceId);
    const key = source?.id ?? finding.sourceId ?? 'uncategorized';
    const existingGroup = groups.get(key);

    if (existingGroup) {
      existingGroup.findings.push(finding);
      return;
    }

    groups.set(key, { source, findings: [finding] });
  });

  return Array.from(groups.values());
}

export function FindingsList({ categories, findings, embedded = false }: FindingsListProps) {
  if (findings.length === 0) {
    return (
      <EmptyState
        title="No findings yet"
        description="When analysis returns signals, they will appear here grouped by category and source."
      />
    );
  }

  return (
    <section className={`space-y-3 ${embedded ? 'pl-2' : ''}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-black text-slate-950 dark:text-white">Findings</h2>
        <span className="text-[11px] font-semibold text-slate-500 dark:text-teal-100/60">
          {findings.length} total
        </span>
      </div>

      <div className="space-y-4">
        {categories.map((category) => {
          const categoryFindings = findings.filter((finding) => finding.categoryId === category.id);
          if (categoryFindings.length === 0) return null;

          return (
            <section key={category.id} className="space-y-2">
              {!embedded && (
                <h3 className="text-xs font-black uppercase tracking-wide text-slate-500 dark:text-teal-100/60">
                  {category.label}
                </h3>
              )}

              {groupFindingsBySource(category, categoryFindings).map((group) => {
                const sourceLabel = group.source?.label ?? 'Other source';
                const evidenceCount = group.source?.evidenceCount;
                const summary = sourceSummary(group.source);

                return (
                  <div key={`${category.id}-${sourceLabel}`} className="space-y-2">
                    <div className="flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-teal-800/70 dark:bg-[#061f24]">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-bold text-slate-900 dark:text-white">
                          {sourceLabel}
                        </p>
                        {summary && (
                          <p className="truncate text-[11px] text-slate-500 dark:text-teal-100/60">
                            {summary}
                          </p>
                        )}
                      </div>
                      {typeof evidenceCount === 'number' && (
                        <span className="shrink-0 text-[11px] font-semibold text-slate-500 dark:text-teal-100/60">
                          {evidenceCount} signals
                        </span>
                      )}
                    </div>

                    <div className="space-y-2">
                      {group.findings.map((finding) => (
                        <FindingCard key={finding.id} finding={finding} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </section>
          );
        })}
      </div>
    </section>
  );
}
