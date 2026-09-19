import type { ScamAnalysis } from '@/src/types/analysis';

interface HeaderProps {
  analysis?: ScamAnalysis;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onBack?: () => void;
}

export function Header({ analysis, theme, onToggleTheme, onBack }: HeaderProps) {
  const storeName = analysis?.store.name ?? 'Scam Check';
  const domain = analysis?.store.domain ?? 'Check this store';

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-teal-800 dark:bg-[#061f24]/95">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="mt-0.5 shrink-0 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-[11px] font-black text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[#007889] dark:border-teal-700 dark:bg-[#082a31] dark:text-teal-100 dark:hover:bg-[#0a4758]"
            >
              Back
            </button>
          )}

          <div className="min-w-0">
            <p className="text-[11px] font-black uppercase tracking-wide text-[#007889] dark:text-teal-300">
              Scam Check
            </p>
            <h1 className="mt-0.5 truncate text-base font-black text-slate-950 dark:text-white">
              {storeName}
            </h1>
            <p className="truncate text-xs font-medium text-slate-500 dark:text-teal-100/65">
              {domain}
            </p>
            {analysis?.product?.name && (
              <p className="mt-1 truncate text-xs text-slate-600 dark:text-teal-100/75">
                {analysis.product.name}
                {analysis.product.price ? ` - ${analysis.product.price}` : ''}
              </p>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          className="shrink-0 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-black text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[#007889] dark:border-teal-700 dark:bg-[#082a31] dark:text-teal-100 dark:hover:bg-[#0a4758]"
        >
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>
    </header>
  );
}
