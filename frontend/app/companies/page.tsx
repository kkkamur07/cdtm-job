import { CompaniesBoard } from "@/components/companies/companies-board";
import { buildCompanyBoardItems } from "@/lib/format-company";
import { fetchCompanies, fetchPublishedJobs } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Companies",
  description: "Employers hiring through the CDTM job board.",
};

export default async function CompaniesPage() {
  const [companiesPage, jobsPage] = await Promise.all([fetchCompanies(), fetchPublishedJobs()]);
  const companies = buildCompanyBoardItems(companiesPage.items, jobsPage.items);

  return <CompaniesBoard companies={companies} />;
}
