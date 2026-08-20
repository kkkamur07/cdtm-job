"use client";

import Link from "next/link";

const footerLinks = [
  { href: "/jobs", label: "Jobs" },
  { href: "/jobs/alerts", label: "Job alerts" },
  { href: "/companies", label: "Companies" },
  { href: "/seekers", label: "Seekers" },
  { href: "/post-job", label: "Post a job" },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-zinc-200 bg-white py-8">
      <div className="mx-auto max-w-6xl space-y-4 px-4 text-center sm:px-6">
        <nav
          className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm font-medium text-zinc-600"
          aria-label="Footer"
        >
          {footerLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="transition-colors hover:text-cdtm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <p className="text-sm text-zinc-500">
          Center for Digital Technology and Management · 2026 · Job board for students and partners
        </p>
      </div>
    </footer>
  );
}
