interface ErrorStateProps {
  message?: string;
  onRetry: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="space-y-4 px-4 py-5">
      <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-rose-950 dark:border-rose-800/70 dark:bg-rose-950/60 dark:text-rose-100">
        <p className="text-sm font-bold">Unable to complete analysis.</p>
        <p className="mt-1 text-xs leading-5 opacity-80">
          {message ?? 'The request could not be completed. Please try again.'}
        </p>
      </div>

      <button
        type="button"
        onClick={onRetry}
        className="w-full rounded-md bg-[#007889] px-3 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-[#026876] focus:outline-none focus:ring-2 focus:ring-[#007889] focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-[#061f24]"
      >
        Try again
      </button>
    </div>
  );
}
