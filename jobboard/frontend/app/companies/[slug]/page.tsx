import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CompanyOpenRoles } from "@/components/companies/company-open-roles";
import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { CompanyAvatar } from "@/components/ui/company-avatar";
import { DetailField } from "@/components/ui/detail-field";
import {
  companyDisplayDescription,
  formatCompanyHq,
  formatCompanySizeBand,
} from "@/lib/format-company";
import { fetchCompanyBySlug, fetchPublishedJobsForCompany } from "@/lib/data/api";
import { safeUrl } from "@/lib/safe-url";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const company = await fetchCompanyBySlug(slug);
    return {
      title: company.name,
      description: company.short_description ?? undefined,
    };
  } catch {
    return { title: "Company" };
  }
}

export default async function CompanyPage({ params }: Props) {
  const { slug } = await params;
  let company;
  try {
    company = await fetchCompanyBySlug(slug);
  } catch {
    notFound();
  }

  const jobsPage = await fetchPublishedJobsForCompany(company.id);
  const hq = formatCompanyHq(company);
  const sizeLabel = formatCompanySizeBand(company.company_size_band);
  const about = companyDisplayDescription(company);
  const websiteUrl = safeUrl(company.website_url);
  const careersUrl = safeUrl(company.careers_page_url);
  const linkedinUrl = safeUrl(company.linkedin_url);

  return (
    <div className="space-y-8">
      <BackLink href="/companies">All companies</BackLink>

      <header className="border-b border-zinc-200 pb-8 pl-5 border-l-4 border-l-cdtm">
        <p className="text-eyebrow mb-4">Company</p>
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
          <CompanyAvatar
            name={company.name}
            logoUrl={company.logo_url}
            className="h-16 w-16 text-base"
          />
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <h1 className="font-display text-[2rem] font-medium leading-[1.12] tracking-[-0.025em] text-zinc-900 sm:text-[2.125rem]">
                {company.name}
              </h1>
              {company.legal_name && company.legal_name !== company.name && (
                <p className="mt-1 text-sm text-zinc-500">{company.legal_name}</p>
              )}
            </div>
            {company.short_description && (
              <p className="text-lead max-w-2xl">{company.short_description}</p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {company.industry && <Badge variant="muted">{company.industry}</Badge>}
              <Badge variant="muted">{sizeLabel}</Badge>
              <Badge variant="muted">{hq}</Badge>
              {company.is_cdtm_startup && <Badge variant="accent">CDTM startup</Badge>}
            </div>
          </div>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[1fr_17.5rem] lg:items-start">
        <div className="space-y-8">
          <section aria-labelledby="company-about-heading">
            <h2 id="company-about-heading" className="text-section-label mb-4">
              About
            </h2>
            <p className="text-prose">{about}</p>
          </section>

          <section aria-labelledby="company-roles-heading">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="company-roles-heading" className="text-section-label">
                  Open roles
                </h2>
                <p className="mt-1 text-sm text-zinc-500">
                  {jobsPage.total} published {jobsPage.total === 1 ? "role" : "roles"} at{" "}
                  {company.name}.
                </p>
              </div>
              <ButtonLink href="/jobs" variant="secondary">
                Browse all jobs
              </ButtonLink>
            </div>
            <CompanyOpenRoles roles={jobsPage.items} />
          </section>
        </div>

        <aside className="lg:sticky lg:top-20">
          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <h2 className="text-section-label">Links</h2>
            <dl className="mt-4 space-y-4">
              {websiteUrl && (
                <DetailField label="Website">
                  <a
                    href={websiteUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-cdtm hover:underline"
                  >
                    {websiteUrl.replace(/^https?:\/\//, "")}
                  </a>
                </DetailField>
              )}
              {careersUrl && (
                <DetailField label="Careers">
                  <a
                    href={careersUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-cdtm hover:underline"
                  >
                    View careers page
                  </a>
                </DetailField>
              )}
              {linkedinUrl && (
                <DetailField label="LinkedIn">
                  <a
                    href={linkedinUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-cdtm hover:underline"
                  >
                    Company profile
                  </a>
                </DetailField>
              )}
              <DetailField label="Headquarters">{hq}</DetailField>
              <DetailField label="Open roles">{jobsPage.total}</DetailField>
            </dl>
            <div className="mt-6">
              <ButtonLink href="/post-job" variant="primary" className="w-full">
                Post a job
              </ButtonLink>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
