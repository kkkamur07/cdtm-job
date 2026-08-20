import type { EmploymentType, ExperienceLevel, JobPublic, WorkArrangement } from "@/lib/api/generated";
import { formatJobLocation } from "@/lib/format-job";

export type JobFilterCriteria = {
  query: string;
  arrangements: ReadonlySet<WorkArrangement> | WorkArrangement[];
  levels: ReadonlySet<ExperienceLevel> | ExperienceLevel[];
  employment: ReadonlySet<EmploymentType> | EmploymentType[];
};

function asArray<T>(value: ReadonlySet<T> | T[]): T[] {
  return Array.isArray(value) ? value : [...value];
}

export function filterJobs(
  jobs: JobPublic[],
  criteria: JobFilterCriteria,
  companyNameById: Record<string, string> = {},
): JobPublic[] {
  let result = jobs;
  const q = criteria.query.trim().toLowerCase();

  if (q) {
    result = result.filter((job) => {
      const company = companyNameById[job.company_id] ?? "";
      const location = formatJobLocation(job) ?? "";
      return (
        job.title.toLowerCase().includes(q) ||
        company.toLowerCase().includes(q) ||
        location.toLowerCase().includes(q) ||
        (job.summary?.toLowerCase().includes(q) ?? false)
      );
    });
  }

  const arrangements = asArray(criteria.arrangements);
  const levels = asArray(criteria.levels);
  const employment = asArray(criteria.employment);

  if (arrangements.length > 0) {
    result = result.filter((job) => arrangements.includes(job.work_arrangement));
  }
  if (levels.length > 0) {
    result = result.filter((job) => levels.includes(job.experience_level));
  }
  if (employment.length > 0) {
    result = result.filter((job) => employment.includes(job.employment_type));
  }

  return result;
}

export function countMatchingJobs(
  jobs: JobPublic[],
  criteria: JobFilterCriteria,
  companyNameById: Record<string, string> = {},
): number {
  return filterJobs(jobs, criteria, companyNameById).length;
}
