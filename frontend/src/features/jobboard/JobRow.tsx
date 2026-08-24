import Link from "next/link";
import { memo } from "react";

import { AvatarCircle } from "@/components/MemberAvatar";
import { firstName } from "@/lib/format";
import CompanyLogo from "./CompanyLogo";
import type { JobRowData } from "./jobData";

/**
 * One role in the jobs list. The whole row is the link target.
 *
 * Memoized because the board re-renders on every keystroke in the search box
 * and every tick of a filter, while a row only changes when its own job does.
 * The rows come straight off the server payload, so their identities are
 * stable and the comparison is a pointer check.
 */
function JobRow({ job, compact = false }: { job: JobRowData; compact?: boolean }) {
    return (
        <li className="cv-row">
            <Link href={job.href} className="jrow">
                <CompanyLogo name={job.company} logoUrl={job.logoUrl} px={compact ? 40 : 48} />

                <div className="min-w-0">
                    <h3>{job.title}</h3>
                    <p className="co truncate">
                        {compact
                            ? [job.company, job.location].filter(Boolean).join(" · ")
                            : job.company}
                    </p>

                    {!compact && (
                        <>
                            <div className="badges">
                                <span className="badge accent">{job.employmentType}</span>
                                <span className="badge">{job.workArrangement}</span>
                                <span className="badge muted">{job.experienceLevel}</span>
                                {job.isCdtmStartup && (
                                    <span className="badge muted">CDTM startup</span>
                                )}
                                {job.salary && (
                                    <span className="badge sal sm:hidden">{job.salary}</span>
                                )}
                            </div>
                            <Via job={job} />
                        </>
                    )}
                </div>

                <div className="right hidden sm:grid">
                    {job.posted && <span>{job.posted}</span>}
                    {!compact && job.location && <span>{job.location}</span>}
                    {!compact && job.salary && <span className="sal">{job.salary}</span>}
                </div>
            </Link>
        </li>
    );
}

export default memo(JobRow);

/**
 * The line under the badges, in order of usefulness: the member who posted the
 * role, failing that a member who works there and can be asked about it,
 * failing that where the listing came from.
 */
function Via({ job }: { job: JobRowData }) {
    const person = job.postedBy ?? job.insider;
    if (!person) return <p className="via mt-2.5">From the CDTM Job Board</p>;

    return (
        <p className="via mt-2.5">
            <AvatarCircle
                name={person.name}
                avatar={person.avatar ? { sm: person.avatar, lg: person.avatar } : null}
                px={18}
            />
            {job.postedBy ? (
                <>
                    Posted by <b className="font-medium text-ink">{person.name}</b>
                </>
            ) : (
                <>
                    Ask <b className="font-medium text-ink">{firstName(person.name)}</b>, who works
                    there
                </>
            )}
        </p>
    );
}
