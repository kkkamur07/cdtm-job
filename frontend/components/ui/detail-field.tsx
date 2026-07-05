import type { ReactNode } from "react";

type DetailFieldProps = {
  label: string;
  children: ReactNode;
};

export function DetailField({ label, children }: DetailFieldProps) {
  return (
    <div>
      <dt className="text-section-label">{label}</dt>
      <dd className="mt-1 text-zinc-800">{children}</dd>
    </div>
  );
}
