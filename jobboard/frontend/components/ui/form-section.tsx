import type { ReactNode } from "react";

type FormSectionProps = {
  step: number;
  title: string;
  description?: string;
  children: ReactNode;
};

export function FormSection({ step, title, description, children }: FormSectionProps) {
  return (
    <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 bg-zinc-50/40 px-5 py-4 sm:px-6">
        <div className="flex items-start gap-3">
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-cdtm text-xs font-bold text-white"
            aria-hidden
          >
            {step}
          </span>
          <div>
            <h2 className="font-display text-lg font-medium tracking-tight text-zinc-900">
              {title}
            </h2>
            {description && (
              <p className="mt-1 text-sm leading-relaxed text-zinc-600">{description}</p>
            )}
          </div>
        </div>
      </div>
      <div className="space-y-5 px-5 py-5 sm:px-6">{children}</div>
    </section>
  );
}

type SegmentedOption<T extends string> = {
  value: T;
  label: string;
  disabled?: boolean;
};

type SegmentedControlProps<T extends string> = {
  name: string;
  value: T;
  options: SegmentedOption<T>[];
  onChange: (value: T) => void;
};

export function SegmentedControl<T extends string>({
  name,
  value,
  options,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="group"
      aria-label={name}
      className="inline-flex w-full max-w-md rounded-lg border border-zinc-200 bg-zinc-50/80 p-1 sm:w-auto"
    >
      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            disabled={option.disabled}
            onClick={() => onChange(option.value)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition sm:flex-none sm:px-4 ${
              active
                ? "bg-white text-cdtm shadow-sm ring-1 ring-zinc-200/80"
                : "text-zinc-600 hover:text-zinc-900"
            } disabled:cursor-not-allowed disabled:opacity-50`}
            aria-pressed={active}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
