import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: ReactNode;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div
      role="status"
      className="flex flex-col items-center rounded-xl border border-dashed border-zinc-200 bg-white px-6 py-14 text-center"
    >
      <div
        className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-white text-zinc-400 ring-1 ring-inset ring-zinc-200"
        aria-hidden
      >
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
          />
        </svg>
      </div>
      <h2 className="font-display text-lg font-medium text-zinc-900">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-zinc-600">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
