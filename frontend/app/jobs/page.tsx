import type { Metadata } from "next";

import { JobCard } from "@/components/job-card";
import { fetchCompanies, fetchPublishedJobs } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Jobs",
};

export default async function JobsPage() {
  const [jobsPage, companiesPage] = await Promise.all([fetchPublishedJobs(), fetchCompanies()]);
  const companyById = new Map(companiesPage.items.map((c) => [c.id, c.name]));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Open roles
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          {jobsPage.total} published {jobsPage.total === 1 ? "listing" : "listings"}
        </p>
      </div>
      {jobsPage.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400">
          No published jobs yet. Check back soon or{" "}
          <a href="/post-job" className="font-medium text-cdtm underline dark:text-cdtm-bright">
            post a role
          </a>
          .
        </p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-1">
          {jobsPage.items.map((job) => (
            <li key={job.id}>
              <JobCard job={job} companyName={companyById.get(job.company_id) ?? null} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
