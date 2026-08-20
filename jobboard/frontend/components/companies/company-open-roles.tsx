import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { formatJobLocation, formatLabel, formatPostedAgo } from "@/lib/format-job";
import type { JobPublic } from "@/lib/api/generated";

type CompanyOpenRolesProps = {
  roles: JobPublic[];
};

export function CompanyOpenRoles({ roles }: CompanyOpenRolesProps) {
  if (roles.length === 0) {
    return (
      <p className="text-sm text-zinc-500">No open roles listed right now. Check back soon.</p>
    );
  }

  return (
    <ul className="overflow-hidden rounded-xl border border-zinc-200 bg-white" role="list">
      {roles.map((job) => {
        const location = formatJobLocation(job);
        const posted = formatPostedAgo(job.published_at ?? job.created_at);
        return (
          <li key={job.id} className="border-b border-zinc-200 last:border-b-0">
            <Link
              href={`/jobs/${job.id}`}
              className="block px-5 py-4 transition-colors hover:bg-cdtm/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cdtm"
            >
              <h3 className="font-display text-[0.9375rem] font-medium tracking-tight text-zinc-900">
                {job.title}
              </h3>
              {location && <p className="mt-0.5 text-sm text-zinc-500">{location}</p>}
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge variant="accent">{formatLabel(job.employment_type)}</Badge>
                <Badge variant="muted">{formatLabel(job.work_arrangement)}</Badge>
                <Badge variant="muted">{formatLabel(job.experience_level)}</Badge>
              </div>
              {posted && <p className="mt-2 text-xs text-zinc-400">{posted}</p>}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
