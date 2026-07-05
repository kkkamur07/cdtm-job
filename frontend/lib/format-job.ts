import type {
  EmploymentType,
  ExperienceLevel,
  JobPublic,
  WorkArrangement,
} from "@/lib/api/generated";

export const WORK_ARRANGEMENTS: WorkArrangement[] = ["remote", "hybrid", "onsite"];
export const EXPERIENCE_LEVELS: ExperienceLevel[] = ["intern", "entry", "mid", "senior", "lead"];
export const EMPLOYMENT_TYPES: EmploymentType[] = [
  "full_time",
  "part_time",
  "contract",
  "internship",
  "temporary",
  "working_student",
  "freelance",
];

export function formatJobLocation(job: JobPublic): string | null {
  if (job.location_display) return job.location_display;
  const parts = [job.city, job.region, job.country].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

export function formatLabel(value: string): string {
  return value.replaceAll("_", " ");
}

export function formatPostedAgo(date: string | null | undefined): string | null {
  if (!date) return null;
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return null;
  const days = Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 14) return "1 week ago";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
