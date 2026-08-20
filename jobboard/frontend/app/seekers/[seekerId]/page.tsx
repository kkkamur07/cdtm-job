import type { Metadata } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { DetailField } from "@/components/ui/detail-field";
import {
  EducationTimeline,
  LanguageProfile,
} from "@/components/seekers/profile-timeline";
import { fetchSeeker } from "@/lib/data/api";
import { safeUrl } from "@/lib/safe-url";

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

function DetailSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <h2 className="text-section-label">{label}</h2>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default async function SeekerDetailPage({ params }: Props) {
  const { seekerId } = await params;
  let seeker;
  try {
    seeker = await fetchSeeker(seekerId);
  } catch {
    notFound();
  }

  const linkedinUrl = safeUrl(seeker.linkedin_url);
  const portfolioUrl = safeUrl(seeker.portfolio_url);
  const githubUrl = safeUrl(seeker.github_url);
  const resumeUrl = safeUrl(seeker.resume_url);

  return (
    <article className="space-y-8">
      <BackLink href="/seekers">All seekers</BackLink>

      <header className="space-y-3 border-b border-zinc-200 pb-8 pl-5 border-l-4 border-l-cdtm">
        <p className="text-eyebrow">Profile</p>
        <h1 className="font-display text-[2rem] font-medium leading-[1.12] tracking-[-0.025em] text-zinc-900 sm:text-[2.125rem]">
          {seeker.full_name}
        </h1>
        {seeker.headline && <p className="text-lead">{seeker.headline}</p>}
      </header>

      {seeker.bio && (
        <div className="text-prose">{seeker.bio}</div>
      )}

      <dl className="grid gap-4 sm:grid-cols-2">
        {seeker.email && (
          <DetailField label="Email">
            <a href={`mailto:${seeker.email}`} className="font-medium text-cdtm hover:underline">
              {seeker.email}
            </a>
          </DetailField>
        )}
        {seeker.phone && <DetailField label="Phone">{seeker.phone}</DetailField>}
        {seeker.years_of_experience != null && (
          <DetailField label="Experience">{seeker.years_of_experience} years</DetailField>
        )}
        {seeker.open_to_remote != null && (
          <DetailField label="Remote">
            {seeker.open_to_remote ? "Open to remote" : "Not open to remote"}
          </DetailField>
        )}
        {seeker.preferred_work_arrangement && (
          <DetailField label="Work arrangement">
            <span className="capitalize">{seeker.preferred_work_arrangement}</span>
          </DetailField>
        )}
        {seeker.available_from && (
          <DetailField label="Available from">{seeker.available_from}</DetailField>
        )}
      </dl>

      {(seeker.preferred_locations?.length ?? 0) > 0 && (
        <DetailSection label="Preferred locations">
          <p className="text-zinc-800">{(seeker.preferred_locations ?? []).join(", ")}</p>
        </DetailSection>
      )}

      {(seeker.desired_role_titles?.length ?? 0) > 0 && (
        <DetailSection label="Desired roles">
          <ul className="flex flex-wrap gap-2">
            {(seeker.desired_role_titles ?? []).map((t) => (
              <li key={t}>
                <Badge variant="accent">{t}</Badge>
              </li>
            ))}
          </ul>
        </DetailSection>
      )}

      {(seeker.skills?.length ?? 0) > 0 && (
        <DetailSection label="Skills">
          <ul className="flex flex-wrap gap-1.5">
            {(seeker.skills ?? []).map((skill) => (
              <li key={skill}>
                <Badge variant="muted">{skill}</Badge>
              </li>
            ))}
          </ul>
        </DetailSection>
      )}

      {((seeker.languages?.length ?? 0) > 0 || seeker.education_summary) && (
        <section className="space-y-8 border-t border-zinc-200 pt-8">
          {(seeker.languages?.length ?? 0) > 0 && (
            <div>
              <h2 className="text-section-label mb-4">Languages</h2>
              <LanguageProfile languages={seeker.languages ?? []} />
            </div>
          )}

          {seeker.education_summary && (
            <div>
              <h2 className="text-section-label mb-4">Education</h2>
              <EducationTimeline summary={seeker.education_summary} />
            </div>
          )}
        </section>
      )}

      <div className="flex flex-wrap gap-4 border-t border-zinc-200 pt-6">
        {linkedinUrl && (
          <a
            href={linkedinUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline"
          >
            LinkedIn
          </a>
        )}
        {portfolioUrl && (
          <a
            href={portfolioUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline"
          >
            Portfolio
          </a>
        )}
        {githubUrl && (
          <a
            href={githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline"
          >
            GitHub
          </a>
        )}
        {resumeUrl && (
          <a
            href={resumeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-cdtm hover:underline"
          >
            Résumé
          </a>
        )}
      </div>
    </article>
  );
}
