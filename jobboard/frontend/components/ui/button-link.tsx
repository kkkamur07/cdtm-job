import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

const variantClass: Record<ButtonVariant, string> = {
  primary: "bg-cdtm text-white hover:bg-cdtm-hover focus-visible:ring-cdtm",
  secondary:
    "border border-zinc-200 bg-white text-zinc-900 hover:border-zinc-300 focus-visible:ring-cdtm",
  ghost: "text-cdtm hover:bg-cdtm/5 focus-visible:ring-cdtm",
};

const baseClass =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-white";

type ButtonLinkProps = Omit<ComponentProps<typeof Link>, "className"> & {
  children: ReactNode;
  variant?: ButtonVariant;
  className?: string;
};

export function ButtonLink({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonLinkProps) {
  return (
    <Link className={`${baseClass} ${variantClass[variant]} ${className}`} {...props}>
      {children}
    </Link>
  );
}
