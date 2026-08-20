import Link from "next/link";

import { GithubIcon, LinkedInIcon, PortfolioIcon } from "@/components/icons/social-contact";
import { Badge } from "@/components/ui/badge";
import type { SeekerPublic } from "@/lib/api/generated";
import { safeUrl } from "@/lib/safe-url";

const iconLink =
  "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition hover:border-cdtm hover:text-cdtm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm";

function SeekerAvatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white font-display text-sm font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200"
      aria-hidden
    >
      {initial}
    </div>
  );
}

type Props = { seeker: SeekerPublic };

export function SeekerListCard({ seeker: s }: Props) {
  const linkedinUrl = safeUrl(s.linkedin_url);
  const githubUrl = safeUrl(s.github_url);
  const portfolioUrl = safeUrl(s.portfolio_url);
  const hasSocial = !!(linkedinUrl || githubUrl || portfolioUrl);

  return (
    <li className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      <Link
        href={`/seekers/${s.id}`}
        className="group block p-5 transition-colors hover:bg-cdtm/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cdtm"
      >
        <div className="flex items-start gap-4">
          <SeekerAvatar name={s.full_name} />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-lg font-medium tracking-tight text-zinc-900 transition-colors group-hover:text-cdtm">
                  {s.full_name}
                </h2>
                {s.headline && (
                  <p className="mt-1 text-sm font-medium text-zinc-700">{s.headline}</p>
                )}
              </div>
              <span className="shrink-0 text-sm font-medium text-cdtm opacity-0 transition-opacity group-hover:opacity-100">
                View →
              </span>
            </div>
            {s.bio && (
              <p className="mt-2 line-clamp-2 text-sm leading-[1.65] text-zinc-600">{s.bio}</p>
            )}
            {(s.skills?.length ?? 0) > 0 && (
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {(s.skills ?? []).slice(0, 6).map((skill) => (
                  <li key={skill}>
                    <Badge variant="muted">{skill}</Badge>
                  </li>
                ))}
                {(s.skills?.length ?? 0) > 6 && (
                  <li>
                    <Badge variant="muted">+{(s.skills?.length ?? 0) - 6} more</Badge>
                  </li>
                )}
              </ul>
            )}
          </div>
        </div>
      </Link>

      {hasSocial && (
        <div className="flex flex-wrap items-center gap-2 border-t border-zinc-200 bg-white px-5 py-3">
          <span className="text-section-label mr-1">Links</span>
          {linkedinUrl && (
            <a
              href={linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={iconLink}
              aria-label={`${s.full_name} on LinkedIn`}
            >
              <LinkedInIcon className="h-4 w-4" />
            </a>
          )}
          {githubUrl && (
            <a
              href={githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={iconLink}
              aria-label={`${s.full_name} on GitHub`}
            >
              <GithubIcon className="h-4 w-4" />
            </a>
          )}
          {portfolioUrl && (
            <a
              href={portfolioUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={iconLink}
              aria-label={`${s.full_name} portfolio`}
            >
              <PortfolioIcon className="h-4 w-4" />
            </a>
          )}
        </div>
      )}
    </li>
  );
}
