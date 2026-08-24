import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/errors";
import { mediaUrl } from "@/api/media";
import { loadCompany, loadJobByRef, loadMemberIndex, loadMembers } from "@/api/server";
import { getIdentity } from "@/auth/session";
import { AvatarCircle } from "@/components/MemberAvatar";
import CompanyLogo from "@/features/jobboard/CompanyLogo";
import { jobLocation } from "@/features/jobboard/jobData";
import { badgeLabel, formatDate, formatSalary, paragraphs, safeUrl } from "@/lib/format";

// No `dynamic = "force-dynamic"` here. There is no generateStaticParams, and
// every loader reads the request's cookies, so no slug was ever eligible for
// build-time prerendering. What the export did do was imply
// `fetchCache = "force-no-store"`, which turned off the `revalidate: 60/300`
// windows on the job and company reads that serve signed-out visitors.

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params) {
    const { slug } = await params;
    try {
        const job = await loadJobByRef(slug);
        return { title: `${job.title} · CDTM Community` };
    } catch {
        return { title: "Job · CDTM Community" };
    }
}

export default async function JobPage({ params }: Params) {
    const { slug } = await params;

    // The company is named by the job, so its read is chained off the job's
    // promise rather than awaited after it: the request goes out the moment the
    // job lands, and it is one company by id instead of the hundred this page
    // used to pull to name one.
    const jobPromise = loadJobByRef(slug).catch((error) => {
        if (error instanceof ApiError && error.isNotFound) return null;
        throw error;
    });
    const companyPromise = jobPromise.then((job) =>
        job?.company_id ? loadCompany(job.company_id).catch(() => null) : null,
    );

    const [job, company] = await Promise.all([jobPromise, companyPromise]);

    if (!job) notFound();

    const name = company?.name ?? "A CDTM company";
    const location = jobLocation(job);
    const salary = formatSalary(job);
    const applyUrl = safeUrl(job.application_url);
    const cover = job.image_url ? mediaUrl(job.image_url) : null;

    return (
        <div className="shell-wide pb-14">
            <div className="py-3">
                <Link href="/jobs" className="btn btn-ghost btn-sm">
                    ← All jobs
                </Link>
            </div>

            <div className="jdetail">
                <article className="min-w-0">
                    {cover ? (
                        <div className="cover relative overflow-hidden">
                            <Image
                                src={cover}
                                alt=""
                                fill
                                sizes="(min-width: 900px) 760px, 100vw"
                                className="object-cover"
                                priority
                            />
                        </div>
                    ) : (
                        <div className="cover bg-gradient-to-br from-blue-soft to-green-soft" />
                    )}

                    <header className="jhead">
                        <p className="eyebrow">Role</p>
                        <div className="mt-2.5 flex items-start gap-4">
                            <CompanyLogo name={name} logoUrl={company?.logo_url} px={56} />
                            <div className="min-w-0">
                                <h1>{job.title}</h1>
                                <p className="mt-2 text-[14.5px] text-muted">
                                    {company?.slug ? (
                                        <Link
                                            href={`/companies?company=${company.slug}`}
                                            className="font-semibold text-blue"
                                        >
                                            {name}
                                        </Link>
                                    ) : (
                                        <b className="font-semibold text-blue">{name}</b>
                                    )}
                                    {location && (
                                        <>
                                            <span className="mx-1.5 text-line">·</span>
                                            {location}
                                        </>
                                    )}
                                </p>
                                <div className="mt-3.5 flex flex-wrap gap-1.5">
                                    <span className="badge accent">
                                        {badgeLabel(job.employment_type)}
                                    </span>
                                    <span className="badge">
                                        {badgeLabel(job.work_arrangement)}
                                    </span>
                                    <span className="badge muted">
                                        {badgeLabel(job.experience_level)}
                                    </span>
                                    {job.valid_through && (
                                        <span className="badge muted">
                                            Apply by {formatDate(job.valid_through)}
                                        </span>
                                    )}
                                    {job.visa_sponsorship && (
                                        <span className="badge muted">Visa sponsorship</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </header>

                    {job.summary && <p className="lead">{job.summary}</p>}

                    {job.description && (
                        <section className="prose mt-7">
                            <h2 className="label">About the role</h2>
                            {paragraphs(job.description).map((part) => (
                                <p key={part.key}>{part.text}</p>
                            ))}
                        </section>
                    )}

                    {job.must_have_skills?.length ? (
                        <section className="prose mt-6">
                            <h2 className="label">What they are looking for</h2>
                            <ul>
                                {job.must_have_skills.map((skill) => (
                                    <li key={skill}>{skill}</li>
                                ))}
                            </ul>
                        </section>
                    ) : null}

                    {job.nice_to_have_skills?.length ? (
                        <section className="prose mt-6">
                            <h2 className="label">Nice to have</h2>
                            <ul>
                                {job.nice_to_have_skills.map((skill) => (
                                    <li key={skill}>{skill}</li>
                                ))}
                            </ul>
                        </section>
                    ) : null}
                </article>

                <aside className="side">
                    <div className="card panel">
                        <h2 className="label">Apply</h2>
                        {(applyUrl || job.application_email) && (
                            <p className="mt-1.5 text-[13px] text-muted">
                                Use the link or e-mail below to reach the hiring team.
                            </p>
                        )}
                        {applyUrl && (
                            <a
                                href={applyUrl}
                                target="_blank"
                                rel="noreferrer noopener"
                                className="btn btn-primary mt-3.5 w-full"
                            >
                                Open application
                            </a>
                        )}
                        {job.application_email && (
                            <p className="mt-2.5 text-center text-[13px] font-medium text-blue">
                                <a href={`mailto:${job.application_email}`}>{job.application_email}</a>
                            </p>
                        )}
                        {salary && (
                            <p className="mt-2.5 text-center text-[13px] text-muted">{salary}</p>
                        )}
                        {!applyUrl && !job.application_email && (
                            <p className="mt-1.5 text-[13px] text-muted">
                                No application link was given. Ask the person who posted it.
                            </p>
                        )}
                    </div>

                    <Suspense fallback={null}>
                        <PostedBy memberId={job.posted_by_member_id} />
                    </Suspense>

                    <Suspense fallback={null}>
                        <PeopleAtCompany name={name} />
                    </Suspense>
                </aside>
            </div>
        </div>
    );
}

/**
 * The poster, in its own boundary.
 *
 * It used to be awaited above the return, which held the two sidebar panels
 * below behind a lookup neither of them needs. Suspended here, all three start
 * as soon as the job is back and race each other.
 *
 * The directory is members-only, so a signed-out reader would only get a 401.
 * The job itself stays public.
 */
async function PostedBy({ memberId }: { memberId: string | null | undefined }) {
    const { accessToken } = await getIdentity();
    if (!memberId || !accessToken) return null;

    const members = await loadMemberIndex([memberId]).catch(() => null);
    const poster = members?.get(memberId);
    if (!poster) return null;

    return (
        <div className="card panel owner">
            <h2 className="label">Posted by</h2>
            <div className="insider mt-2">
                <AvatarCircle name={poster.name} avatar={poster.avatar} px={44} />
                <div className="min-w-0">
                    <div className="n truncate">{poster.name}</div>
                    <div className="s truncate">
                        {[poster.title, poster.company].filter(Boolean).join(", ")}
                    </div>
                </div>
            </div>
            <Link href={`/members/${poster.slug}`} className="btn mt-3.5 w-full">
                Open entry
            </Link>
        </div>
    );
}

/**
 * Streamed in its own boundary: this lookup needs the company name, so it can
 * only start once the job has arrived. Suspending it here keeps the rest of the
 * page from waiting on it.
 */
async function PeopleAtCompany({ name }: { name: string }) {
    const { accessToken } = await getIdentity();
    if (!accessToken) return null;

    const result = await loadMembers({ company: name, limit: 6 }).catch(() => null);
    if (!result?.items.length) return null;

    return (
        <div className="card panel">
            <h2 className="label">CDTM people at {name}</h2>
            <p className="mt-1.5 text-[12.5px] text-muted">
                Ask one of them what it is like inside before you apply.
            </p>
            <ul className="mt-2.5 grid gap-2">
                {result.items.map((member) => (
                    <li key={member.id}>
                        <Link
                            href={`/members/${member.slug}`}
                            className="insider rounded-2xl p-1 hover:bg-cream"
                        >
                            <AvatarCircle name={member.name} avatar={member.avatar} px={32} />
                            <span className="min-w-0">
                                <span className="n block truncate">{member.name}</span>
                                <span className="s block truncate">
                                    {[member.title, member.company].filter(Boolean).join(", ")}
                                </span>
                            </span>
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
}
