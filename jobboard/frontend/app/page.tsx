import { HomeEditorial } from "@/components/home-editorial";
import { fetchCompanies, fetchPublishedJobs, fetchSeekers } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [jobsPage, seekersPage, companiesPage] = await Promise.all([
    fetchPublishedJobs(),
    fetchSeekers(),
    fetchCompanies(),
  ]);

  const stats = [
    { value: jobsPage.total, label: "Open roles", href: "/jobs" },
    { value: seekersPage.total, label: "Seeker profiles", href: "/seekers" },
    { value: companiesPage.total, label: "Companies", href: "/companies" },
  ];

  return <HomeEditorial stats={stats} />;
}
