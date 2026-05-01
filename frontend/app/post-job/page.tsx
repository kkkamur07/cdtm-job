import type { Metadata } from "next";

import { PostJobForm } from "@/components/post-job-form";
import { fetchCompanies } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Post a job",
};

export default async function PostJobPage() {
  const { items: companies } = await fetchCompanies();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Post a job
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Pick an existing company or create one here, then publish the role. For production,
          restrict this flow behind authentication or an API key.
        </p>
      </div>
      <PostJobForm companies={companies} />
    </div>
  );
}
