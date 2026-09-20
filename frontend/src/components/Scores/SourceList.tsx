import { useId, useState } from 'react';
import type { AnalysisSource } from '@/src/types/analysis';
import { formatDisplayPercentage } from '@/src/utils/score';
import { StatusBadge } from '../Shared/StatusBadge';

interface SourceListProps {
  sources: AnalysisSource[];
}

/**
 * Every configured source, including the ones that found nothing.
 *
 * Findings only exist where a source had something to report, so a source that
 * looked and found nothing used to vanish from the panel entirely - leaving
 * 'GPTZero scored the reviews and none were AI', 'GPTZero found no reviews on
 * this page' and 'GPTZero has no API key' all rendering as an unexplained gap.
 * Those are three different answers and the user has to be able to tell them
 * apart.
 */

/** Map the backend's ScoreStatus to something worth reading. */
const STATUS_TEXT: Record<string, string> = {
  available: 'Reported',
  'insufficient-data': 'Not enough data',
  unavailable: 'Not checked',
  error: 'Source error',
};

function statusText(metadata: Record<string, unknown> | undefined): string | undefined {
  const status = metadata?.scoringStatus;
  return typeof status === 'string' ? (STATUS_TEXT[status] ?? status) : undefined;
}

/**
 * One line saying what the source actually did, built from whatever it
 * reported. Keyed on the metadata present rather than on the source id, so a
 * new source gets a sensible line without touching this file.
 */
function activityLine(metadata: Record<string, unknown> | undefined): string | undefined {
  if (!metadata) return undefined;

  // The source never ran and said why (no reviews, no API key).
  if (typeof metadata.reason === 'string') return metadata.reason;
  if (typeof metadata.error === 'string') return metadata.error;

  const parts: string[] = [];
  if (typeof metadata.scored === 'number') {
    parts.push(`${metadata.scored} review${metadata.scored === 1 ? '' : 's'} scored`);
  }
  if (typeof metadata.flagged === 'number') {
    parts.push(`${metadata.flagged} flagged as AI`);
  }
  if (typeof metadata.confidence === 'string') {
    parts.push(`${metadata.confidence} confidence`);
  }
  return parts.length > 0 ? parts.join(' · ') : undefined;
}

function formatKey(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return JSON.stringify(value);
}

/** Flatten one level so `extraction: {received: 5, ...}` reads as rows. */
function detailRows(metadata: Record<string, unknown> | undefined): [string, unknown][] {
  if (!metadata) return [];

  return Object.entries(metadata).flatMap(([key, value]): [string, unknown][] => {
    if (key === 'scoringStatus') return [];
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return Object.entries(value as Record<string, unknown>).map(
        ([childKey, childValue]) => [`${formatKey(key)} · ${formatKey(childKey)}`, childValue],
      );
    }
    return [[formatKey(key), value]];
  });
}

function SourceRow({ source }: { source: AnalysisSource }) {
  const [isOpen, setIsOpen] = useState(false);
  const detailId = useId();
  const rows = detailRows(source.metadata);
  const activity = activityLine(source.metadata);
  const scored = typeof source.riskScore === 'number' && (source.maxScore ?? 0) > 0;

  return (
    <li className="rounded-md border border-slate-200 bg-white p-3 dark:border-teal-800/70 dark:bg-[#082a31]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold text-slate-950 dark:text-white">{source.label}</p>
          <p className="mt-0.5 text-[11px] font-medium text-slate-500 dark:text-teal-100/60">
            {statusText(source.metadata) ?? source.scoreLabel}
            {source.weight &&
              ` · Weight ${formatDisplayPercentage(source.weight.value, source.weight.maxValue)}`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs font-black text-slate-950 dark:text-white">
            {scored ? formatDisplayPercentage(source.riskScore!, source.maxScore!) : '—'}
          </span>
          <StatusBadge status={source.status} label={scored ? source.status : 'no score'} />
        </div>
      </div>

      {activity && (
        <p className="mt-2 text-[11px] leading-4 text-slate-600 dark:text-teal-100/70">{activity}</p>
      )}

      {rows.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={isOpen}
            aria-controls={detailId}
            onClick={() => setIsOpen((current) => !current)}
            className="mt-2 rounded-sm text-[11px] font-black text-[#007889] underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-[#007889] dark:text-teal-200"
          >
            {isOpen ? 'Hide details' : 'Show details'}
          </button>

          {isOpen && (
            <dl
              id={detailId}
              className="mt-2 grid grid-cols-1 gap-1 text-[11px] text-slate-500 dark:text-teal-100/60"
            >
              {rows.map(([key, value]) => (
                <div key={key} className="flex min-w-0 justify-between gap-2">
                  <dt className="shrink-0 font-semibold">{key}</dt>
                  <dd className="min-w-0 truncate">{formatValue(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </>
      )}
    </li>
  );
}

export function SourceList({ sources }: SourceListProps) {
  if (sources.length === 0) return null;

  return (
    <section className="space-y-2">
      <h3 className="text-xs font-black uppercase tracking-wide text-slate-500 dark:text-teal-100/60">
        Sources
      </h3>
      <ul className="space-y-2">
        {sources.map((source) => (
          <SourceRow key={source.id} source={source} />
        ))}
      </ul>
    </section>
  );
}
