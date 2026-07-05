import type { Metadata } from "next";

import { JobsBoard } from "@/components/jobs/jobs-board";
import { fetchCompanies, fetchPublishedJobs } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Jobs",
};

export default async function JobsPage() {
  const [jobsPage, companiesPage] = await Promise.all([fetchPublishedJobs(), fetchCompanies()]);
  const companyById = Object.fromEntries(
    companiesPage.items.map((c) => [c.id, { name: c.name, logoUrl: c.logo_url ?? null }]),
  );

  return <JobsBoard jobs={jobsPage.items} companyById={companyById} />;
}
