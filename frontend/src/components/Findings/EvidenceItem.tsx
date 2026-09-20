import type { Evidence } from '@/src/types/analysis';

interface EvidenceItemProps {
  evidence: Evidence;
}

function formatMetadataValue(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  return JSON.stringify(value);
}

export function EvidenceItem({ evidence }: EvidenceItemProps) {
  const metadataEntries = evidence.metadata ? Object.entries(evidence.metadata) : [];

  return (
    <li className="rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-teal-800/70 dark:bg-[#061f24]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold text-slate-950 dark:text-white">{evidence.label}</p>
          <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-[11px] font-medium text-slate-500 dark:text-teal-100/60">
            {evidence.source && <span>{evidence.source}</span>}
            {evidence.date && <span>{evidence.date}</span>}
          </div>
        </div>
        {evidence.url && (
          <a
            href={evidence.url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 rounded-sm text-[11px] font-bold text-[#007889] underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-[#007889] dark:text-teal-200"
          >
            View source
          </a>
        )}
      </div>

      {evidence.excerpt && (
        <p className="mt-2 break-words text-xs leading-5 text-slate-700 dark:text-teal-50/80">
          {evidence.excerpt}
        </p>
      )}

      {metadataEntries.length > 0 && (
        <dl className="mt-2 grid grid-cols-1 gap-1 text-[11px] text-slate-500 dark:text-teal-100/60">
          {metadataEntries.map(([key, value]) => (
            <div key={key} className="flex min-w-0 justify-between gap-2">
              <dt className="shrink-0 font-semibold capitalize">{key.replace(/([A-Z])/g, ' $1')}</dt>
              <dd className="min-w-0 truncate">{formatMetadataValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}
