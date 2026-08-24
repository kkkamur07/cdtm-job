"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/placeholders";
import CompanyLogo from "@/features/jobboard/CompanyLogo";

/** What a company card draws, flattened on the server. */
export type CompanyCardData = {
    id: string;
    name: string;
    logoUrl: string | null;
    industry: string | null;
    where: string | null;
    shortDescription: string | null;
    sizeLabel: string | null;
    isCdtmStartup: boolean;
    openRoles: number;
    website: string | null;
};

/**
 * The search box, and nothing else.
 *
 * The companies and their open-role counts are fetched on the server, so this
 * island holds one string. There are a few hundred companies at most, so
 * filtering them here is instant and costs no request per keystroke, which is
 * what the old client-side version spent to answer the same question.
 */
export default function CompaniesBrowser({ companies }: { companies: CompanyCardData[] }) {
    const [query, setQuery] = useState("");

    const shown = useMemo(() => {
        const needle = query.trim().toLowerCase();
        if (!needle) return companies;
        return companies.filter((company) =>
            `${company.name} ${company.industry ?? ""} ${company.where ?? ""}`
                .toLowerCase()
                .includes(needle),
        );
    }, [companies, query]);

    return (
        <>
            <input
                type="search"
                className="input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search companies"
                aria-label="Search companies"
            />

            <p className="text-[12.5px] text-muted" aria-live="polite">
                Showing <b className="tabular-nums text-ink">{shown.length}</b> of{" "}
                {companies.length} {companies.length === 1 ? "company" : "companies"}
            </p>

            {shown.length === 0 ? (
                <div className="card">
                    <EmptyState title="No companies match that" />
                </div>
            ) : (
                <ul className="grid gap-3 sm:grid-cols-2">
                    {shown.map((company) => (
                        <li key={company.id} className="card grid content-start gap-2.5 p-4">
                            <div className="flex items-start gap-3">
                                <CompanyLogo name={company.name} logoUrl={company.logoUrl} />
                                <div className="min-w-0">
                                    <h2 className="text-[15px] leading-snug font-semibold">
                                        {company.name}
                                    </h2>
                                    <p className="text-[12.5px] text-muted">
                                        {[company.industry, company.where]
                                            .filter(Boolean)
                                            .join(" · ")}
                                    </p>
                                </div>
                            </div>

                            {company.shortDescription && (
                                <p className="text-[13px] text-muted">{company.shortDescription}</p>
                            )}

                            <div className="flex flex-wrap items-center gap-1.5">
                                {company.sizeLabel && (
                                    <span className="pill pill-muted">{company.sizeLabel}</span>
                                )}
                                {company.isCdtmStartup && (
                                    <span className="pill pill-green">CDTM startup</span>
                                )}
                                {company.openRoles > 0 && (
                                    <Link href="/jobs" className="pill pill-accent">
                                        {company.openRoles} open{" "}
                                        {company.openRoles === 1 ? "role" : "roles"}
                                    </Link>
                                )}
                                {company.website && (
                                    <a
                                        href={company.website}
                                        target="_blank"
                                        rel="noreferrer noopener"
                                        className="text-[12.5px] font-medium text-blue hover:underline"
                                    >
                                        Website
                                    </a>
                                )}
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </>
    );
}
