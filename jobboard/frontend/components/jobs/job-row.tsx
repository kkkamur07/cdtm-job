import Link from "next/link";

import { CompanyAvatar } from "@/components/ui/company-avatar";
import { Badge } from "@/components/ui/badge";
import { formatJobLocation, formatLabel, formatPostedAgo } from "@/lib/format-job";
import type { JobPublic } from "@/lib/api/generated";

type JobRowProps = {
  job: JobPublic;
  companyName?: string | null;
  companyLogoUrl?: string | null;
};

export function JobRow({ job, companyName, companyLogoUrl }: JobRowProps) {
  const location = formatJobLocation(job);
  const posted = formatPostedAgo(job.published_at ?? job.created_at);
  const displayCompany = companyName ?? "Company";

  return (
    <Link
      href={`/jobs/${job.id}`}
      className="group grid gap-2 px-5 py-4 transition-colors hover:bg-cdtm/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cdtm sm:grid-cols-[auto_1fr_auto_auto] sm:items-center sm:gap-4"
    >
      <CompanyAvatar name={displayCompany} logoUrl={companyLogoUrl} className="hidden sm:flex" />
      <div className="min-w-0">
        <h2 className="font-display text-[0.9375rem] font-medium tracking-tight text-zinc-900 transition-colors group-hover:text-cdtm">
          {job.title}
        </h2>
        <p className="mt-0.5 text-sm text-zinc-500">{displayCompany}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          <Badge variant="accent">{formatLabel(job.employment_type)}</Badge>
          <Badge variant="muted">{formatLabel(job.work_arrangement)}</Badge>
          <Badge variant="muted">{formatLabel(job.experience_level)}</Badge>
        </div>
      </div>
      {posted && (
        <span className="text-xs text-zinc-400 sm:text-right">{posted}</span>
      )}
      {location && (
        <span className="text-sm text-zinc-500 sm:text-right">{location}</span>
      )}
    </Link>
  );
}
