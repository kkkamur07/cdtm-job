import Link from "next/link";

import {
    loadCompanies,
    loadJobs,
    loadMemberIndex,
    loadMembersAtCompanies,
} from "@/api/server";
import JobsBrowser from "@/features/jobboard/JobsBrowser";
import { toJobRow } from "@/features/jobboard/jobData";

// Forces per-request rendering instead of build-time prerendering, since this
// page reads via revalidate-based loaders (loadJobs, loadCompanies) and there
// is no live backend at build time. The revalidate windows on the individual
// fetches still govern the Data Cache, so runtime caching is unchanged.
export const dynamic = "force-dynamic";

export const metadata = { title: "Jobs · CDTM Community" };

/**
 * The job board.
 *
 * Jobs and companies are independent, so they go out together. The posters can
 * only be looked up once the jobs are back, since their ids come off the jobs,
 * so that is one dependent request rather than a fan-out. It is allowed to
 * fail: without it the rows simply lose their "posted by" line.
 */
export default async function JobsPage() {
    const [jobs, companies] = await Promise.all([
        loadJobs({ status: "published", limit: 100 }),
        loadCompanies({ limit: 100 }),
    ]);

    const byCompany = new Map(companies.items.map((company) => [company.id, company]));
    const names = [
        ...new Set(
            jobs.items
                .map((job) => (job.company_id ? byCompany.get(job.company_id)?.name : null))
                .filter((name): name is string => Boolean(name)),
        ),
    ];

    // Both of these need the jobs, so they are the second wave, and they go out
    // together. Each is one request: the posters come back from a batched id
    // lookup, and the insiders from a batched name lookup that used to be one
    // request per distinct company. Both may fail without taking the board with
    // them; the rows simply lose those two lines.
    const [members, byInsider] = await Promise.all([
        loadMemberIndex(jobs.items.map((job) => job.posted_by_member_id)).catch(() => null),
        loadMembersAtCompanies(names).catch(() => null),
    ]);

    const rows = jobs.items.map((job) => {
        const company = job.company_id ? byCompany.get(job.company_id) : undefined;
        return toJobRow(
            job,
            company,
            job.posted_by_member_id ? members?.get(job.posted_by_member_id) : null,
            company ? (byInsider?.get(company.name) ?? null) : null,
        );
    });

    return (
        <div className="shell-wide pb-14">
            <div className="bhead pt-3">
                <div className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <p className="eyebrow">Open roles</p>
                        <h1>Browse listings</h1>
                        <p className="desc">
                            Roles from CDTM partners, alumni companies and members&rsquo; own teams.
                            Every listing shows who inside CDTM you can ask.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Link href="/companies" className="btn">
                            Companies
                        </Link>
                        <Link href="/jobs/new" className="btn btn-primary">
                            Post a job
                        </Link>
                    </div>
                </div>
            </div>

            <JobsBrowser jobs={rows} total={jobs.total} />
        </div>
    );
}
