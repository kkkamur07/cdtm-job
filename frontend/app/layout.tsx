import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { HomeVideoBackdrop } from "@/components/home-video-backdrop";
import { MainArea } from "@/components/main-area";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "CDTM Job Board",
    template: "%s · CDTM Job Board",
  },
  description:
    "Center for Digital Technology and Management (2026) — job openings and talent from the CDTM community.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="relative min-h-[100dvh] bg-zinc-50 font-sans text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
        <HomeVideoBackdrop />
        <div className="relative z-10 flex min-h-[100dvh] flex-col">
          <SiteHeader />
          <MainArea>{children}</MainArea>
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
