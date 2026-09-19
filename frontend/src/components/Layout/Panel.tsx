import type { ReactNode } from 'react';

interface PanelProps {
  children: ReactNode;
  theme: 'light' | 'dark';
}

export function Panel({ children, theme }: PanelProps) {
  return (
    <div
      className={`${theme} h-full bg-slate-100 font-sans text-sm text-slate-900 dark:bg-[#061f24] dark:text-teal-50`}
    >
      <div className="flex h-full w-full min-w-0 flex-col overflow-hidden">{children}</div>
    </div>
  );
}
