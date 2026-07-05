import type { ReactNode } from "react";

export function MainArea({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 bg-gradient-to-b from-cdtm/[0.035] to-white to-[8rem] px-4 py-10 sm:px-6">
      {children}
    </main>
  );
}
