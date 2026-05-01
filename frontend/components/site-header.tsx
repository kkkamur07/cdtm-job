"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/jobs", label: "Jobs" },
  { href: "/seekers", label: "Seekers" },
  { href: "/post-job", label: "Post a job" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const isHome = pathname === "/";

  return (
    <header
      className={
        isHome
          ? "relative z-10 border-b border-white/10 bg-transparent backdrop-blur-md"
          : "relative z-10 border-b border-zinc-200/80 bg-white/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90"
      }
    >
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/brand/cdtm-logo.png"
            alt="Center for Digital Technology and Management, 2026"
            width={1879}
            height={806}
            className={`h-9 w-auto max-w-[200px] object-contain object-left sm:max-w-[240px] sm:h-10 ${isHome ? "drop-shadow-md brightness-0 invert" : ""}`}
            priority
          />
          <span
            className={`hidden border-l pl-3 text-sm font-medium tracking-tight sm:inline ${
              isHome
                ? "border-white/25 text-white/90"
                : "border-zinc-200 text-zinc-600 dark:border-zinc-700 dark:text-zinc-400"
            }`}
          >
            Job Board
          </span>
        </Link>
        <nav className="flex flex-wrap items-center gap-1 sm:gap-4">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={
                isHome
                  ? "rounded-md px-2 py-1.5 text-sm font-medium text-white/95 drop-shadow-sm transition-colors hover:bg-white/10 hover:text-white"
                  : "rounded-md px-2 py-1.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-cdtm dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-cdtm-bright"
              }
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
