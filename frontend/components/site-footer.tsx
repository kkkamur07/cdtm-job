"use client";

import { usePathname } from "next/navigation";

export function SiteFooter() {
  const pathname = usePathname();
  const isHome = pathname === "/";

  return (
    <footer
      className={
        isHome
          ? "relative z-10 mt-auto border-t border-white/15 bg-black/25 py-8 text-center text-sm text-white/75 backdrop-blur-md"
          : "relative z-10 mt-auto border-t border-zinc-200/80 bg-zinc-50/80 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950/50 dark:text-zinc-400"
      }
    >
      <p>
        Center for Digital Technology and Management · 2026 · Job board for students and partners
      </p>
    </footer>
  );
}
