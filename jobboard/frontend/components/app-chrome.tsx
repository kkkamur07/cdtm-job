"use client";

import type { ReactNode } from "react";

import { MainArea } from "@/components/main-area";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export function AppChrome({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-[100dvh] flex-col">
      <SiteHeader />
      <MainArea>{children}</MainArea>
      <SiteFooter />
    </div>
  );
}
