import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, Newsreader } from "next/font/google";

import { AppChrome } from "@/components/app-chrome";

import "./globals.css";

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "CDTM Job Board",
    template: "%s · CDTM Job Board",
  },
  description:
    "Center for Digital Technology and Management (2026). Job openings and talent from the CDTM community.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${newsreader.variable} ${inter.variable} h-full antialiased`}
    >
      <body className="min-h-[100dvh] bg-white font-sans text-zinc-900">
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
