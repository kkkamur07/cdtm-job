import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { CompanyAvatar } from "@/components/ui/company-avatar";
import { fetchCompany, fetchJob } from "@/lib/data/api";
import { formatJobLocation, formatLabel } from "@/lib/format-job";
import { safeUrl } from "@/lib/safe-url";

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

export default async function JobDetailPage({ params }: Props) {
  const { jobId } = await params;
  let job;
  try {
    job = await fetchJob(jobId);
  } catch {
    notFound();
  }

  let company;
  try {
    company = await fetchCompany(job.company_id);
  } catch {
    company = undefined;
  }
  const location = formatJobLocation(job);
  const hasApply = !!(safeUrl(job.application_url) || job.application_email);
  const applicationUrl = safeUrl(job.application_url);
  const companyProfileSlug = company?.slug;

  return (
    <div className="space-y-8">
      <BackLink href="/jobs">All jobs</BackLink>

      <header className="border-b border-zinc-200 pb-8 pl-5 border-l-4 border-l-cdtm">
        <p className="text-eyebrow mb-2">Role</p>
        <div className="flex items-start gap-4">
          {company && (
            <CompanyAvatar
              name={company.name}
              logoUrl={company.logo_url}
              className="h-12 w-12 text-sm"
            />
          )}
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-[2rem] font-medium leading-[1.12] tracking-[-0.025em] text-zinc-900 sm:text-[2.125rem]">
              {job.title}
            </h1>
            <p className="mt-2 text-meta">
              {company?.name && (
                companyProfileSlug ? (
                  <Link
                    href={`/companies/${companyProfileSlug}`}
                    className="text-meta-strong font-medium text-cdtm hover:underline"
                  >
                    {company.name}
                  </Link>
                ) : (
                  <span className="text-meta-strong">{company.name}</span>
                )
              )}
              {company?.name && location && <span className="mx-2 text-zinc-300">·</span>}
              {location && <span>{location}</span>}
            </p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              <Badge variant="accent">{formatLabel(job.employment_type)}</Badge>
              <Badge>{formatLabel(job.work_arrangement)}</Badge>
              <Badge variant="muted">{formatLabel(job.experience_level)}</Badge>
              <Badge variant="muted">{job.status}</Badge>
            </div>
          </div>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[1fr_17.5rem] lg:items-start">
        <article className="space-y-8">
          {job.summary && (
            <p className="text-lead">{job.summary}</p>
          )}

          <section aria-labelledby="job-description-heading">
            <h2 id="job-description-heading" className="text-section-label mb-4">
              About the role
            </h2>
            <div className="text-prose">{job.description}</div>
          </section>
        </article>

        {hasApply && (
          <aside className="lg:sticky lg:top-20">
            <div className="rounded-xl border border-zinc-200 bg-white p-6">
              <h2 className="text-section-label">Apply</h2>
              <p className="mt-2 text-sm leading-[1.65] text-zinc-600">
                Ready to move forward? Use the link or email below to reach the hiring team.
              </p>
              <div className="mt-4 space-y-3">
                {applicationUrl && (
                  <ButtonLink
                    href={applicationUrl}
                    variant="primary"
                    className="w-full"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open application
                  </ButtonLink>
                )}
                {job.application_email && (
                  <a
                    href={`mailto:${job.application_email}`}
                    className="block text-center text-sm font-medium text-cdtm hover:underline"
                  >
                    {job.application_email}
                  </a>
                )}
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
