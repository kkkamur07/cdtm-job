import type { ReactNode } from "react";

export function FilterGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-wider text-zinc-500">
        {title}
      </h3>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

export function FilterCheckbox({
  label,
  count,
  checked,
  onChange,
}: {
  label: string;
  count: number;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={`flex cursor-pointer items-center justify-between gap-2 py-1.5 text-sm ${
        checked ? "font-medium text-cdtm" : "text-zinc-700"
      }`}
    >
      <span className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={onChange}
          className="accent-cdtm"
        />
        {label}
      </span>
      <span className="text-xs tabular-nums text-zinc-400">{count}</span>
    </label>
  );
}

export function FilterPanelHead({
  activeCount,
  onClear,
}: {
  activeCount: number;
  onClear: () => void;
}) {
  return (
    <div className="mb-4 flex items-center justify-between border-b border-zinc-200 pb-3">
      <h2 className="text-sm font-semibold text-zinc-900">Filters</h2>
      {activeCount > 0 && (
        <button type="button" onClick={onClear} className="text-xs font-medium text-cdtm hover:underline">
          Clear all
        </button>
      )}
    </div>
  );
}

export function FilterChips({
  chips,
  onClearAll,
}: {
  chips: { id: string; label: string; clear: () => void }[];
  onClearAll: () => void;
}) {
  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <span
          key={chip.id}
          className="inline-flex items-center gap-1 rounded-full bg-cdtm/10 px-2.5 py-0.5 text-xs font-medium text-cdtm"
        >
          {chip.label}
          <button
            type="button"
            onClick={chip.clear}
            className="opacity-70 hover:opacity-100"
            aria-label={`Remove ${chip.label} filter`}
          >
            ×
          </button>
        </span>
      ))}
      <button type="button" onClick={onClearAll} className="text-xs font-medium text-zinc-500 hover:text-cdtm">
        Clear all
      </button>
    </div>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
}) {
  return (
    <label className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm sm:max-w-xs">
      <svg
        className="h-4 w-4 shrink-0 text-zinc-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        className="min-w-0 flex-1 border-0 bg-transparent outline-none"
      />
    </label>
  );
}

export function SortSelect({
  value,
  onChange,
  options,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  ariaLabel: string;
}) {
  return (
    <label className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm">
      <svg
        className="h-4 w-4 text-zinc-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
      </svg>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={ariaLabel}
        className="border-0 bg-transparent outline-none"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function MobileFilterSheet({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 lg:hidden"
      role="dialog"
      aria-label="Filters"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-auto rounded-t-xl bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Filters</h2>
          <button type="button" className="text-sm font-medium text-cdtm" onClick={onClose}>
            Done
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
