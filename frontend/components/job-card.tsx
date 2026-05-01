import Link from "next/link";

import type { JobPublic } from "@/lib/api/generated";

type JobCardProps = {
  job: JobPublic;
  companyName?: string | null;
};

function formatLocation(job: JobPublic): string | null {
  if (job.location_display) return job.location_display;
  const parts = [job.city, job.region, job.country].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

export function JobCard({ job, companyName }: JobCardProps) {
  const location = formatLocation(job);
  return (
    <Link
      href={`/jobs/${job.id}`}
      className="group block rounded-xl border border-zinc-200/90 bg-white p-5 shadow-sm transition-shadow hover:border-zinc-300 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700"
    >
      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900 group-hover:text-cdtm dark:text-zinc-50 dark:group-hover:text-cdtm-bright">
          {job.title}
        </h2>
        {(companyName || location) && (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {[companyName, location].filter(Boolean).join(" · ")}
          </p>
        )}
        {job.summary && (
          <p className="line-clamp-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            {job.summary}
          </p>
        )}
        <div className="flex flex-wrap gap-2 pt-1 text-xs font-medium text-zinc-500 dark:text-zinc-500">
          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 dark:bg-zinc-900">
            {job.employment_type.replaceAll("_", " ")}
          </span>
          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 dark:bg-zinc-900">
            {job.work_arrangement}
          </span>
          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 dark:bg-zinc-900">
            {job.experience_level}
          </span>
        </div>
      </div>
    </Link>
  );
}
