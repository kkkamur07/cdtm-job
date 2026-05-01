import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchCompanies, fetchJob } from "@/lib/data/api";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ jobId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { jobId } = await params;
  try {
    const job = await fetchJob(jobId);
    return { title: job.title };
  } catch {
    return { title: "Job" };
  }
}

function formatLocation(job: Awaited<ReturnType<typeof fetchJob>>): string | null {
  if (job.location_display) return job.location_display;
  const parts = [job.city, job.region, job.country].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

export default async function JobDetailPage({ params }: Props) {
  const { jobId } = await params;
  let job;
  try {
    job = await fetchJob(jobId);
  } catch {
    notFound();
  }

  const { items: companies } = await fetchCompanies();
  const company = companies.find((c) => c.id === job.company_id);
  const location = formatLocation(job);

  return (
    <article className="space-y-8">
      <div>
        <Link
          href="/jobs"
          className="text-sm font-medium text-cdtm hover:underline dark:text-cdtm-bright"
        >
          ← All jobs
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {job.title}
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          {[company?.name, location].filter(Boolean).join(" · ") || "Role details"}
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium text-zinc-600 dark:text-zinc-400">
          <span className="rounded-full bg-zinc-200/80 px-2.5 py-1 dark:bg-zinc-800">
            {job.employment_type.replaceAll("_", " ")}
          </span>
          <span className="rounded-full bg-zinc-200/80 px-2.5 py-1 dark:bg-zinc-800">
            {job.work_arrangement}
          </span>
          <span className="rounded-full bg-zinc-200/80 px-2.5 py-1 dark:bg-zinc-800">
            {job.experience_level}
          </span>
          <span className="rounded-full bg-zinc-200/80 px-2.5 py-1 capitalize dark:bg-zinc-800">
            {job.status}
          </span>
        </div>
      </div>

      {job.summary && (
        <p className="text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">{job.summary}</p>
      )}

      <div className="prose prose-zinc max-w-none dark:prose-invert">
        <div className="whitespace-pre-wrap text-zinc-800 dark:text-zinc-200">{job.description}</div>
      </div>

      {(job.application_url || job.application_email) && (
        <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Apply</h2>
          {job.application_url && (
            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block font-medium text-cdtm hover:underline dark:text-cdtm-bright"
            >
              Application link
            </a>
          )}
          {job.application_email && (
            <p className="mt-2">
              <a
                href={`mailto:${job.application_email}`}
                className="font-medium text-cdtm hover:underline dark:text-cdtm-bright"
              >
                {job.application_email}
              </a>
            </p>
          )}
        </div>
      )}
    </article>
  );
}
