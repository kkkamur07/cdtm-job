import Link from "next/link";
import type { ComponentProps } from "react";

type BackLinkProps = Omit<ComponentProps<typeof Link>, "className"> & {
  children: React.ReactNode;
};

export function BackLink({ children, ...props }: BackLinkProps) {
  return (
    <Link
      className="group inline-flex items-center gap-1.5 text-sm font-medium text-cdtm transition-colors hover:text-cdtm-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2"
      {...props}
    >
      <svg
        className="h-4 w-4 transition-transform group-hover:-translate-x-0.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
      </svg>
      {children}
    </Link>
  );
}
