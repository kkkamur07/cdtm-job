"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ButtonLink } from "@/components/ui/button-link";

const nav = [
  {
    href: "/jobs",
    label: "Jobs",
    match: (path: string) =>
      path === "/jobs" || (path.startsWith("/jobs/") && !path.startsWith("/jobs/alerts")),
  },
  {
    href: "/jobs/alerts",
    label: "Alerts",
    match: (path: string) => path.startsWith("/jobs/alerts"),
  },
  {
    href: "/companies",
    label: "Companies",
    match: (path: string) => path.startsWith("/companies") && path !== "/companies/new",
  },
  { href: "/seekers", label: "Seekers", match: (path: string) => path.startsWith("/seekers") },
  { href: "/post-job", label: "Post", match: (path: string) => path.startsWith("/post-job") },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-3.5 sm:px-6">
        <Link
          href="/"
          className="flex min-w-0 items-center gap-4 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2"
        >
          <Image
            src="/brand/cdtm-mark.svg"
            alt="CDTM"
            width={52}
            height={39}
            className="h-11 w-auto shrink-0"
            priority
          />
          <span className="hidden min-w-0 text-left sm:block">
            <span className="font-display block text-base font-medium leading-tight tracking-tight text-zinc-900">
              Job Board
            </span>
            <span className="mt-0.5 block font-sans text-[0.6875rem] font-medium leading-snug text-zinc-500">
              Center for Digital Technology and Management
            </span>
          </span>
        </Link>

        <div className="flex shrink-0 items-center gap-2">
          <nav
            className="hidden rounded-lg border border-zinc-200 p-1 sm:flex"
            aria-label="Main"
          >
            {nav.map((item) => {
              const active = item.match(pathname);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    active
                      ? "rounded-md bg-white px-3 py-1.5 text-sm font-medium text-cdtm shadow-sm"
                      : "rounded-md px-3 py-1.5 text-sm font-medium text-zinc-600 transition-colors hover:text-zinc-900"
                  }
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <ButtonLink href="/post-job" variant="primary" className="hidden sm:inline-flex">
            Post a job
          </ButtonLink>
        </div>
      </div>
    </header>
  );
}
