import Link from "next/link";

import { loadCompanies, loadJobs } from "@/api/server";
import { humanise, safeUrl } from "@/lib/format";
import CompaniesBrowser, { type CompanyCardData } from "./Client";

// No `dynamic = "force-dynamic"` here. Reading the request's cookies already
// makes this route dynamic, and the export additionally implied
// `fetchCache = "force-no-store"`, which turned off the `revalidate: 300`
// window on `loadCompanies` that a signed-out visitor is meant to be served
// from.

export const metadata = { title: "Companies · CDTM Community" };

const SIZE_LABELS: Record<string, string> = {
    startup: "Startup",
    smb: "SMB",
    mid: "Mid-market",
    enterprise: "Enterprise",
};

/**
 * Companies hiring through the board, with their open role count.
 *
 * Both reads happen here rather than in the browser: the whole page used to be
 * a client component that fetched a hundred companies and a hundred jobs after
 * hydration just to count roles per company. The counting is the same
 * arithmetic either way, and doing it on the server means the page arrives
 * drawn instead of arriving as a skeleton.
 */
export default async function CompaniesPage() {
    const [companies, jobs] = await Promise.all([
        loadCompanies({ limit: 100 }),
        // The counts are a nicety; a company card without one still reads.
        loadJobs({ status: "published", limit: 100 }).catch(() => null),
    ]);

    const openRoles = new Map<string, number>();
    for (const job of jobs?.items ?? []) {
        if (!job.company_id) continue;
        openRoles.set(job.company_id, (openRoles.get(job.company_id) ?? 0) + 1);
    }

    const cards: CompanyCardData[] = companies.items.map((company) => ({
        id: company.id,
        name: company.name,
        logoUrl: company.logo_url ?? null,
        industry: company.industry ?? null,
        where: [company.hq_city, company.hq_country].filter(Boolean).join(", ") || null,
        shortDescription: company.short_description ?? null,
        sizeLabel: company.company_size_band
            ? (SIZE_LABELS[company.company_size_band] ?? humanise(company.company_size_band))
            : null,
        isCdtmStartup: Boolean(company.is_cdtm_startup),
        openRoles: openRoles.get(company.id) ?? 0,
        website: safeUrl(company.website_url),
    }));

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <p className="eyebrow">CDTM job board</p>
                    <h1 className="text-xl font-semibold">Companies</h1>
                    <p className="text-[13px] text-muted">Where CDTM people work, build and hire.</p>
                </div>
                <Link href="/jobs" className="btn">
                    Open roles
                </Link>
            </header>

            <CompaniesBrowser companies={cards} />
        </div>
    );
}
