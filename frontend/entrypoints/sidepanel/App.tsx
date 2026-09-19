import { useEffect, useState } from 'react';
import { OverallRisk } from '@/src/components/Analysis/OverallRisk';
import { RiskSummary } from '@/src/components/Analysis/RiskSummary';
import { Header } from '@/src/components/Layout/Header';
import { Panel } from '@/src/components/Layout/Panel';
import { ErrorState } from '@/src/components/Shared/ErrorState';
import { LoadingState } from '@/src/components/Shared/LoadingState';
import { loadingSteps } from '@/src/data/mockAnalysis';
import { analysisService, type AnalysisRequest } from '@/src/services/analysisService';
import type { ScamAnalysis } from '@/src/types/analysis';

type ViewState = 'idle' | 'loading' | 'success' | 'error';
type Theme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'scam-check-theme';

function getPreferredTheme(): Theme {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (storedTheme === 'light' || storedTheme === 'dark') return storedTheme;

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export default function App() {
  const [viewState, setViewState] = useState<ViewState>('idle');
  const [analysis, setAnalysis] = useState<ScamAnalysis>();
  const [error, setError] = useState<string>();
  const [lastRequest, setLastRequest] = useState<AnalysisRequest>({ mode: 'standard' });
  const [theme, setTheme] = useState<Theme>(() => getPreferredTheme());

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  async function runAnalysis(request: AnalysisRequest = { mode: 'standard' }) {
    setViewState('loading');
    setError(undefined);

    try {
      const [activeTab] = await browser.tabs.query({ active: true, currentWindow: true });
      const nextRequest = {
        ...request,
        currentUrl: request.currentUrl ?? activeTab?.url,
      };
      setLastRequest(nextRequest);

      const nextAnalysis = await analysisService.getAnalysis(nextRequest);
      setAnalysis(nextAnalysis);
      setViewState('success');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed.');
      setViewState('error');
    }
  }

  function returnToLanding() {
    setViewState('idle');
    setAnalysis(undefined);
    setError(undefined);
  }

  return (
    <Panel theme={theme}>
      <Header
        analysis={analysis}
        theme={theme}
        onToggleTheme={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
        onBack={viewState === 'idle' ? undefined : returnToLanding}
      />

      <main className="min-h-0 flex-1 overflow-y-auto">
        {viewState === 'idle' && <IdleState onRun={runAnalysis} />}

        {viewState === 'loading' && <LoadingState steps={loadingSteps} />}

        {viewState === 'error' && (
          <ErrorState message={error} onRetry={() => void runAnalysis(lastRequest)} />
        )}

        {viewState === 'success' && analysis && (
          <div className="space-y-5 px-4 py-4">
            <OverallRisk analysis={analysis} />
            <RiskSummary analysis={analysis} />
          </div>
        )}
      </main>
    </Panel>
  );
}

function IdleState({ onRun }: { onRun: (request?: AnalysisRequest) => void }) {
  return (
    <div className="px-4 py-5">
      <section className="rounded-md border border-slate-200 bg-white p-4 shadow-sm dark:border-teal-700/60 dark:bg-[#082a31]">
        <p className="text-base font-black text-slate-950 dark:text-white">Check this store</p>
        <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-teal-100/70">
          Run a compact risk review for suspicious reputation and review-quality signals.
        </p>

        <button
          type="button"
          onClick={() => onRun({ mode: 'standard' })}
          className="mt-4 w-full rounded-md bg-[#007889] px-3 py-2 text-sm font-black text-white shadow-sm transition hover:bg-[#026876] focus:outline-none focus:ring-2 focus:ring-[#007889] focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-[#082a31]"
        >
          Run Sham Scanner
        </button>

      </section>
    </div>
  );
}
