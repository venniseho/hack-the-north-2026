interface EmptyStateProps {
  title: string;
  description: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-center dark:border-teal-700/60 dark:bg-[#082a31]/60">
      <p className="text-sm font-bold text-slate-900 dark:text-white">{title}</p>
      <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-teal-100/70">{description}</p>
    </div>
  );
}
