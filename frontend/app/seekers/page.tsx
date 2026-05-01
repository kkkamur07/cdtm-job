import type { Metadata } from "next";
import Link from "next/link";

import { GithubIcon, LinkedInIcon, PortfolioIcon } from "@/components/icons/social-contact";
import { SeekerListCard } from "@/components/seeker-list-card";
import { fetchSeekers } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Discover candidates",
};

export default async function SeekersPage() {
  const page = await fetchSeekers();

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Discover great candidates
          </h1>
          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2 text-zinc-600 dark:text-zinc-400">
            <span>Open LinkedIn, GitHub, or portfolio links when candidates share them.</span>
            <span
              className="inline-flex items-center gap-2 text-cdtm dark:text-cdtm-bright"
              aria-hidden
            >
              <LinkedInIcon />
              <GithubIcon />
              <PortfolioIcon />
            </span>
          </p>
        </div>
        <Link
          href="/seekers/new"
          className="inline-flex w-fit items-center justify-center rounded-lg bg-cdtm px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-cdtm-hover"
        >
          Add your profile
        </Link>
      </div>

      {page.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400">
          No seeker profiles yet.{" "}
          <Link href="/seekers/new" className="font-medium text-cdtm dark:text-cdtm-bright">
            Create the first one
          </Link>
          .
        </p>
      ) : (
        <ul className="grid gap-4">
          {page.items.map((s) => (
            <SeekerListCard key={s.id} seeker={s} />
          ))}
        </ul>
      )}
    </div>
  );
}
