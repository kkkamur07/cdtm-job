import type { Metadata } from "next";

import { JobAlertsPanel } from "@/components/jobs/job-alerts-panel";
import { BackLink } from "@/components/ui/back-link";
import { ButtonLink } from "@/components/ui/button-link";
import { PageHeader } from "@/components/ui/page-header";
import { fetchCompanies, fetchPublishedJobs } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Job alerts",
  description: "Set up personalized email digests for new roles on the CDTM job board.",
};

export default async function JobAlertsPage() {
  const [jobsPage, companiesPage] = await Promise.all([fetchPublishedJobs(), fetchCompanies()]);
  const companyNameById = Object.fromEntries(
    companiesPage.items.map((c) => [c.id, c.name]),
  );

  return (
    <div className="space-y-8">
      <BackLink href="/jobs">Jobs</BackLink>

      <PageHeader
        eyebrow="Stay in the loop"
        title="Personalized job alerts"
        description="Tell us who you are, which roles you want, and how often to hear about new matches. Demo only — alerts are saved in this browser."
        action={
          <ButtonLink href="/jobs" variant="secondary">
            Browse jobs
          </ButtonLink>
        }
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_17.5rem] lg:items-start">
        <JobAlertsPanel jobs={jobsPage.items} companyNameById={companyNameById} />

        <aside className="lg:sticky lg:top-20">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
            <h2 className="text-section-label">How it works</h2>
            <ol className="mt-4 space-y-3 text-sm leading-relaxed text-zinc-600">
              <li>1. Add your name and email.</li>
              <li>2. Choose keywords and filters for the roles you care about.</li>
              <li>3. Pick weekly or daily — we show how many jobs match today.</li>
            </ol>
            <p className="mt-4 text-xs leading-relaxed text-zinc-500">
              In production, matching listings would be emailed on your schedule. No messages are
              sent in this demo.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
