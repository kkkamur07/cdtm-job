import Link from "next/link";

import { GithubIcon, LinkedInIcon, PortfolioIcon } from "@/components/icons/social-contact";
import type { SeekerPublic } from "@/lib/api/generated";

const iconLink =
  "inline-flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition hover:border-cdtm hover:text-cdtm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400 dark:hover:border-cdtm-bright dark:hover:text-cdtm-bright";

type Props = { seeker: SeekerPublic };

export function SeekerListCard({ seeker: s }: Props) {
  const hasSocial = !!(s.linkedin_url || s.github_url || s.portfolio_url);

  return (
    <li className="overflow-hidden rounded-xl border border-zinc-200/90 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <Link
        href={`/seekers/${s.id}`}
        className="group block p-5 transition-colors hover:bg-zinc-50/80 dark:hover:bg-zinc-900/50"
      >
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900 transition-colors group-hover:text-cdtm dark:text-zinc-50 dark:group-hover:text-cdtm-bright">
          {s.full_name}
        </h2>
        {s.headline && (
          <p className="mt-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">{s.headline}</p>
        )}
        {s.bio && (
          <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            {s.bio}
          </p>
        )}
        {(s.skills?.length ?? 0) > 0 && (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {(s.skills ?? []).map((skill) => (
              <li
                key={skill}
                className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
              >
                {skill}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-xs font-medium text-cdtm dark:text-cdtm-bright">View profile →</p>
      </Link>

      {hasSocial && (
        <div className="flex flex-wrap items-center gap-2 border-t border-zinc-200 px-5 py-3 dark:border-zinc-800">
          <span className="mr-1 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
            Links
          </span>
          {s.linkedin_url && (
            <a
              href={s.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className={iconLink}
              aria-label={`${s.full_name} on LinkedIn`}
            >
              <LinkedInIcon className="h-5 w-5" />
            </a>
          )}
          {s.github_url && (
            <a
              href={s.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className={iconLink}
              aria-label={`${s.full_name} on GitHub`}
            >
              <GithubIcon className="h-5 w-5" />
            </a>
          )}
          {s.portfolio_url && (
            <a
              href={s.portfolio_url}
              target="_blank"
              rel="noopener noreferrer"
              className={iconLink}
              aria-label={`${s.full_name} portfolio`}
            >
              <PortfolioIcon className="h-5 w-5" />
            </a>
          )}
        </div>
      )}
    </li>
  );
}
