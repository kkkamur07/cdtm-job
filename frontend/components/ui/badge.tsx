import type { ReactNode } from "react";

type BadgeVariant = "default" | "accent" | "muted";

const variantClass: Record<BadgeVariant, string> = {
  default: "bg-white text-zinc-700 ring-1 ring-inset ring-zinc-200",
  accent: "bg-cdtm/10 text-cdtm",
  muted: "bg-white text-zinc-500 ring-1 ring-inset ring-zinc-200",
};

type BadgeProps = {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
};

export function Badge({ children, variant = "default", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium capitalize ${variantClass[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
