import Link from "next/link";

import { ButtonLink } from "@/components/ui/button-link";

type HomeEditorialProps = {
  stats: { value: number; label: string; href: string }[];
};

const pathways = [
  {
    href: "/jobs",
    title: "Browse open roles",
    description:
      "Startups and partners hiring CDTM talent, filtered by arrangement and level.",
    cta: "View jobs",
  },
  {
    href: "/seekers",
    title: "Discover candidates",
    description: "Profiles from the community with skills, links, and availability.",
    cta: "Meet seekers",
  },
  {
    href: "/companies",
    title: "Explore companies",
    description: "Teams behind the listings: culture, focus, and open roles.",
    cta: "View companies",
  },
  {
    href: "/post-job",
    title: "Post a position",
    description: "List a role for your company and reach motivated builders.",
    cta: "Create listing",
  },
] as const;

export function HomeEditorial({ stats }: HomeEditorialProps) {
  return (
    <div className="space-y-16 pb-4 lg:space-y-20 lg:pb-8">
      <section className="max-w-2xl" aria-labelledby="home-heading">
        <p className="text-eyebrow">CDTM Job Board · 2026</p>
        <h1
          id="home-heading"
          className="font-display mt-5 text-[2.5rem] font-medium leading-[1.08] tracking-[-0.03em] text-zinc-900 sm:text-5xl lg:text-[3.5rem]"
        >
          Find the next rocketship.
        </h1>
        <p className="text-lead mt-5 max-w-xl">
          Browse roles from CDTM partners and innovators, discover candidates from the
          community, or publish a listing for your team.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <ButtonLink href="/jobs" variant="primary">
            Browse jobs
          </ButtonLink>
          <ButtonLink href="/seekers" variant="secondary">
            Seeker directory
          </ButtonLink>
          <ButtonLink href="/post-job" variant="ghost">
            Post a job
          </ButtonLink>
        </div>
      </section>

      <section aria-label="Board statistics">
        <ul className="grid gap-3 sm:grid-cols-3" role="list">
          {stats.map((stat) => (
            <li key={stat.label}>
              <Link
                href={stat.href}
                aria-label={`${stat.value} ${stat.label}`}
                className="group block rounded-xl border border-zinc-200 bg-white px-5 py-4 shadow-sm transition hover:border-cdtm/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2"
              >
                <p className="font-display text-3xl font-semibold tabular-nums tracking-tight text-zinc-900 transition-colors group-hover:text-cdtm">
                  {stat.value}
                </p>
                <p className="mt-1 text-sm text-zinc-500">{stat.label}</p>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section
        className="rounded-xl border border-cdtm/20 bg-cdtm/[0.04] px-6 py-5 sm:flex sm:items-center sm:justify-between sm:gap-6"
        aria-labelledby="home-alerts-heading"
      >
        <div className="max-w-xl">
          <p className="text-eyebrow">Stay in the loop</p>
          <h2
            id="home-alerts-heading"
            className="font-display mt-2 text-xl font-medium tracking-[-0.02em] text-zinc-900"
          >
            Job alerts
          </h2>
          <p className="mt-2 text-sm leading-[1.65] text-zinc-600">
            Personalized digests for the roles you care about — name, email, and job preferences.
          </p>
        </div>
        <ButtonLink
          href="/jobs/alerts"
          variant="primary"
          className="mt-4 shrink-0 sm:mt-0"
        >
          Set up alerts
        </ButtonLink>
      </section>

      <section aria-labelledby="home-pathways-heading">
        <div className="mb-6 max-w-xl">
          <h2
            id="home-pathways-heading"
            className="font-display text-[1.625rem] font-medium leading-[1.15] tracking-[-0.02em] text-zinc-900"
          >
            Where do you want to start?
          </h2>
          <p className="mt-2 text-base leading-[1.65] text-zinc-600">
            Four paths into the board: browse roles, meet people, explore employers, or publish.
          </p>
        </div>

        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="list">
          {pathways.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition hover:border-cdtm/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2"
              >
                <span
                  className="absolute inset-y-0 left-0 w-1 bg-cdtm opacity-0 transition-opacity group-hover:opacity-100"
                  aria-hidden
                />
                <h3 className="text-ui-title transition-colors group-hover:text-cdtm">
                  {item.title}
                </h3>
                <p className="mt-2 flex-1 text-sm leading-[1.65] text-zinc-600">
                  {item.description}
                </p>
                <span className="mt-4 text-sm font-medium text-cdtm">{item.cta} →</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
