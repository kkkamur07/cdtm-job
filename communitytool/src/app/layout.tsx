import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CDTM Community",
  description: "Directory of CDTM students and Center Assistants.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
