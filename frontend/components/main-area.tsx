"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

export function MainArea({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isHome = pathname === "/";

  return (
    <main
      className={
        isHome
          ? "relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center px-4 py-12 sm:px-6 sm:py-16"
          : "relative z-10 mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6"
      }
    >
      {children}
    </main>
  );
}
