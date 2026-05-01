import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchSeeker } from "@/lib/data/api";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ seekerId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { seekerId } = await params;
  try {
    const seeker = await fetchSeeker(seekerId);
    return { title: seeker.full_name };
  } catch {
    return { title: "Seeker" };
  }
}

export default async function SeekerDetailPage({ params }: Props) {
  const { seekerId } = await params;
  let seeker;
  try {
    seeker = await fetchSeeker(seekerId);
  } catch {
    notFound();
  }

  return (
    <article className="space-y-8">
      <div>
        <Link
          href="/seekers"
          className="text-sm font-medium text-cdtm hover:underline dark:text-cdtm-bright"
        >
          ← All seekers
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {seeker.full_name}
        </h1>
        {seeker.headline && (
          <p className="mt-2 text-lg text-zinc-700 dark:text-zinc-300">{seeker.headline}</p>
        )}
      </div>

      {seeker.bio && (
        <div className="prose prose-zinc max-w-none dark:prose-invert">
          <p className="whitespace-pre-wrap leading-relaxed text-zinc-800 dark:text-zinc-200">
            {seeker.bio}
          </p>
        </div>
      )}

      <dl className="grid gap-4 sm:grid-cols-2">
        {seeker.email && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Email</dt>
            <dd className="mt-1">
              <a
                href={`mailto:${seeker.email}`}
                className="font-medium text-cdtm hover:underline dark:text-cdtm-bright"
              >
                {seeker.email}
              </a>
            </dd>
          </div>
        )}
        {seeker.phone && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Phone</dt>
            <dd className="mt-1 text-zinc-800 dark:text-zinc-200">{seeker.phone}</dd>
          </div>
        )}
        {seeker.years_of_experience != null && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Experience
            </dt>
            <dd className="mt-1 text-zinc-800 dark:text-zinc-200">
              {seeker.years_of_experience} years
            </dd>
          </div>
        )}
        {seeker.open_to_remote != null && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Remote</dt>
            <dd className="mt-1 text-zinc-800 dark:text-zinc-200">
              {seeker.open_to_remote ? "Open to remote" : "Not open to remote"}
            </dd>
          </div>
        )}
        {seeker.preferred_work_arrangement && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Work arrangement
            </dt>
            <dd className="mt-1 capitalize text-zinc-800 dark:text-zinc-200">
              {seeker.preferred_work_arrangement}
            </dd>
          </div>
        )}
        {seeker.available_from && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Available from
            </dt>
            <dd className="mt-1 text-zinc-800 dark:text-zinc-200">{seeker.available_from}</dd>
          </div>
        )}
      </dl>

      {(seeker.preferred_locations?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Preferred locations
          </h2>
          <p className="mt-2 text-zinc-800 dark:text-zinc-200">
            {(seeker.preferred_locations ?? []).join(", ")}
          </p>
        </div>
      )}

      {(seeker.desired_role_titles?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Desired roles
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {(seeker.desired_role_titles ?? []).map((t) => (
              <li
                key={t}
                className="rounded-full bg-zinc-100 px-3 py-1 text-sm dark:bg-zinc-900 dark:text-zinc-200"
              >
                {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(seeker.skills?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Skills</h2>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {(seeker.skills ?? []).map((skill) => (
              <li
                key={skill}
                className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
              >
                {skill}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(seeker.languages?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Languages</h2>
          <p className="mt-2 text-zinc-800 dark:text-zinc-200">
            {(seeker.languages ?? []).join(", ")}
          </p>
        </div>
      )}

      {seeker.education_summary && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Education</h2>
          <p className="mt-2 whitespace-pre-wrap text-zinc-800 dark:text-zinc-200">
            {seeker.education_summary}
          </p>
        </div>
      )}

      <div className="flex flex-wrap gap-4 border-t border-zinc-200 pt-6 dark:border-zinc-800">
        {seeker.linkedin_url && (
          <a
            href={seeker.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline dark:text-cdtm-bright"
          >
            LinkedIn
          </a>
        )}
        {seeker.portfolio_url && (
          <a
            href={seeker.portfolio_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline dark:text-cdtm-bright"
          >
            Portfolio
          </a>
        )}
        {seeker.github_url && (
          <a
            href={seeker.github_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline dark:text-cdtm-bright"
          >
            GitHub
          </a>
        )}
        {seeker.resume_url && (
          <a
            href={seeker.resume_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline dark:text-cdtm-bright"
          >
            Résumé
          </a>
        )}
      </div>
    </article>
  );
}
