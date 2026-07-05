import type { Metadata } from "next";

import { PostJobForm } from "@/components/post-job-form";
import { PostJobSidebar } from "@/components/post-job-sidebar";
import { BackLink } from "@/components/ui/back-link";
import { PageHeader } from "@/components/ui/page-header";
import { fetchCompanies } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Post a job",
  description: "Publish a role for your company on the CDTM job board.",
};

export default async function PostJobPage() {
  const { items: companies } = await fetchCompanies();

  return (
    <div className="space-y-8">
      <BackLink href="/jobs">Jobs</BackLink>

      <PageHeader
        eyebrow="For companies"
        title="Post a job"
        description="Register your organization (or pick one already on the board), then publish a role for CDTM students and alumni to discover."
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_17.5rem] lg:items-start">
        <PostJobForm companies={companies} />
        <PostJobSidebar />
      </div>
    </div>
  );
}
