import type { Company, JobSummary, Member } from "@/api/types";
import { badgeLabel, compactSalary, timeAgo } from "@/lib/format";

/**
 * What a job row needs, and nothing else.
 *
 * The list is filtered in the browser, so every field here crosses the
 * server-client boundary as JSON. Flattening on the server keeps that payload
 * to what is actually drawn instead of the full job, company and member.
 */
export type JobRowData = {
    id: string;
    href: string;
    title: string;
    company: string;
    companyId: string | null;
    logoUrl: string | null;
    isCdtmStartup: boolean;
    location: string | null;
    city: string | null;
    employmentType: string;
    workArrangement: string;
    experienceLevel: string;
    salary: string | null;
    posted: string | null;
    /** Sortable, unlike the "3 days ago" string. */
    postedAt: string;
    postedBy: RowMember | null;
    /**
     * A CDTM member who works at the company. The mock's "ask X who worked
     * there" line: the point of the board is that there is usually someone
     * inside you can ask before you apply.
     */
    insider: RowMember | null;
};

type RowMember = { name: string; slug: string; avatar: string | null };

function toRowMember(member: Member): RowMember {
    return { name: member.name, slug: member.slug, avatar: member.avatar?.sm ?? null };
}

/**
 * `JobSummary` rather than `Job`: the board reads the list route, which leaves the
 * description and the keyword lists off the row. A whole `Job` still fits, so the
 * detail page can call this with what it already has.
 */
export function jobLocation(job: JobSummary): string | null {
    if (job.location_display) return job.location_display;
    const parts = [job.city, job.region, job.country].filter(Boolean);
    return parts.length ? parts.join(", ") : null;
}

export function toJobRow(
    job: JobSummary,
    company: Company | undefined,
    poster?: Member | null,
    insider?: Member | null,
): JobRowData {
    return {
        id: job.id,
        href: `/jobs/${job.slug ?? job.id}`,
        title: job.title,
        company: company?.name ?? "A CDTM company",
        companyId: job.company_id ?? null,
        logoUrl: company?.logo_url ?? null,
        isCdtmStartup: Boolean(company?.is_cdtm_startup),
        location: jobLocation(job),
        city: job.city ?? null,
        employmentType: badgeLabel(job.employment_type),
        workArrangement: badgeLabel(job.work_arrangement),
        experienceLevel: badgeLabel(job.experience_level),
        salary: compactSalary(job),
        posted: timeAgo(job.published_at ?? job.created_at),
        postedAt: job.published_at ?? job.created_at,
        postedBy: poster ? toRowMember(poster) : null,
        // Never the same person twice: if the poster already works there, the
        // row says "posted by" and stops.
        insider: insider && insider.id !== poster?.id ? toRowMember(insider) : null,
    };
}
