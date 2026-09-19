interface LoadingStateProps {
  steps: string[];
}

export function LoadingState({ steps }: LoadingStateProps) {
  return (
    <div className="space-y-4 px-4 py-5">
      <div>
        <p className="text-base font-bold text-slate-950 dark:text-white">Analyzing store...</p>
        <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-teal-100/70">
          Collecting available signals for this page.
        </p>
      </div>

      <div className="space-y-2">
        {steps.map((step) => (
          <div
            key={step}
            className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 shadow-sm dark:border-teal-700/50 dark:bg-[#082a31]"
          >
            <span className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-teal-500 dark:bg-teal-300" />
            <span className="text-xs font-medium text-slate-700 dark:text-teal-50">{step}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
