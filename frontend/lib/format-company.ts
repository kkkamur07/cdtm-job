import type { CompanyPublic, JobPublic } from "@/lib/api/generated";

export type CompanyBoardItem = CompanyPublic & {
  companySizeLabel: string;
  hqLabel: string;
  openRoles: JobPublic[];
};

const SIZE_LABELS: Record<string, string> = {
  startup: "Startup",
  smb: "SMB",
  mid: "Mid-market",
  enterprise: "Enterprise",
};

export function formatCompanySizeBand(
  band: CompanyPublic["company_size_band"],
): string {
  if (!band) return "Size undisclosed";
  return SIZE_LABELS[band] ?? band.replaceAll("_", " ");
}

export function formatCompanyHq(company: CompanyPublic): string {
  const parts = [company.hq_city, company.hq_region, company.hq_country].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : "Location undisclosed";
}

export function companyDisplayDescription(company: CompanyPublic): string {
  return (
    company.full_description?.trim() ||
    company.short_description?.trim() ||
    "No company description yet."
  );
}

export function buildCompanyBoardItems(
  companies: CompanyPublic[],
  publishedJobs: JobPublic[],
): CompanyBoardItem[] {
  const jobsByCompany = new Map<string, JobPublic[]>();
  for (const job of publishedJobs) {
    const list = jobsByCompany.get(job.company_id) ?? [];
    list.push(job);
    jobsByCompany.set(job.company_id, list);
  }

  return companies.map((company) => ({
    ...company,
    companySizeLabel: formatCompanySizeBand(company.company_size_band),
    hqLabel: formatCompanyHq(company),
    openRoles: jobsByCompany.get(company.id) ?? [],
  }));
}
