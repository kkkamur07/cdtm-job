"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { JobRow } from "@/components/jobs/job-row";
import { ButtonLink } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import {
  FilterCheckbox,
  FilterChips,
  FilterGroup,
  FilterPanelHead,
  MobileFilterSheet,
  SearchField,
  SortSelect,
} from "@/components/ui/filters";
import { filterJobs } from "@/lib/filter-jobs";
import { formatJobLocation, formatLabel, EMPLOYMENT_TYPES, EXPERIENCE_LEVELS, WORK_ARRANGEMENTS } from "@/lib/format-job";
import { toggleSetValue } from "@/lib/set-utils";
import type { EmploymentType, ExperienceLevel, JobPublic, WorkArrangement } from "@/lib/api/generated";

type SortKey = "newest" | "oldest" | "company" | "title";

type CompanySummary = {
  name: string;
  logoUrl?: string | null;
};

type JobsBoardProps = {
  jobs: JobPublic[];
  companyById: Record<string, CompanySummary>;
};

function sortJobs(jobs: JobPublic[], sort: SortKey, companyById: Record<string, CompanySummary>) {
  const copy = [...jobs];
  copy.sort((a, b) => {
    if (sort === "newest") {
      return new Date(b.published_at ?? b.created_at).getTime() - new Date(a.published_at ?? a.created_at).getTime();
    }
    if (sort === "oldest") {
      return new Date(a.published_at ?? a.created_at).getTime() - new Date(b.published_at ?? b.created_at).getTime();
    }
    if (sort === "company") {
      const ca = companyById[a.company_id]?.name ?? "";
      const cb = companyById[b.company_id]?.name ?? "";
      return ca.localeCompare(cb);
    }
    return a.title.localeCompare(b.title);
  });
  return copy;
}

export function JobsBoard({ jobs, companyById }: JobsBoardProps) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [arrangements, setArrangements] = useState<Set<WorkArrangement>>(new Set());
  const [levels, setLevels] = useState<Set<ExperienceLevel>>(new Set());
  const [employment, setEmployment] = useState<Set<EmploymentType>>(new Set());
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const counts = useMemo(() => {
    const arrangement: Record<string, number> = {};
    const level: Record<string, number> = {};
    const employ: Record<string, number> = {};
    for (const j of jobs) {
      arrangement[j.work_arrangement] = (arrangement[j.work_arrangement] ?? 0) + 1;
      level[j.experience_level] = (level[j.experience_level] ?? 0) + 1;
      employ[j.employment_type] = (employ[j.employment_type] ?? 0) + 1;
    }
    return { arrangement, level, employ };
  }, [jobs]);

  const filtered = useMemo(() => {
    const companyNameById = Object.fromEntries(
      Object.entries(companyById).map(([id, c]) => [id, c.name]),
    );
    const result = filterJobs(
      jobs,
      { query, arrangements, levels, employment },
      companyNameById,
    );
    return sortJobs(result, sort, companyById);
  }, [jobs, query, arrangements, levels, employment, sort, companyById]);

  const activeFilterCount = arrangements.size + levels.size + employment.size;

  const toggle = <T,>(set: React.Dispatch<React.SetStateAction<Set<T>>>, value: T) => {
    set((prev) => toggleSetValue(prev, value));
  };

  const clearFilters = () => {
    setArrangements(new Set());
    setLevels(new Set());
    setEmployment(new Set());
    setQuery("");
  };

  const filterPanel = (
    <>
      <FilterPanelHead activeCount={activeFilterCount} onClear={clearFilters} />
      <FilterGroup title="Work arrangement">
        {WORK_ARRANGEMENTS.map((value) => (
          <FilterCheckbox
            key={value}
            label={formatLabel(value)}
            count={counts.arrangement[value] ?? 0}
            checked={arrangements.has(value)}
            onChange={() => toggle(setArrangements, value)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Experience">
        {EXPERIENCE_LEVELS.map((value) => (
          <FilterCheckbox
            key={value}
            label={formatLabel(value)}
            count={counts.level[value] ?? 0}
            checked={levels.has(value)}
            onChange={() => toggle(setLevels, value)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Employment">
        {EMPLOYMENT_TYPES.map((value) => (
          <FilterCheckbox
            key={value}
            label={formatLabel(value)}
            count={counts.employ[value] ?? 0}
            checked={employment.has(value)}
            onChange={() => toggle(setEmployment, value)}
          />
        ))}
      </FilterGroup>
    </>
  );

  const chips: { id: string; label: string; clear: () => void }[] = [];
  arrangements.forEach((v) =>
    chips.push({ id: `arrangement:${v}`, label: formatLabel(v), clear: () => toggle(setArrangements, v) }),
  );
  levels.forEach((v) =>
    chips.push({ id: `level:${v}`, label: formatLabel(v), clear: () => toggle(setLevels, v) }),
  );
  employment.forEach((v) =>
    chips.push({ id: `employment:${v}`, label: formatLabel(v), clear: () => toggle(setEmployment, v) }),
  );

  if (jobs.length === 0) {
    return (
      <EmptyState
        title="No published jobs yet"
        description={
          <>
            Check back soon, or{" "}
            <Link href="/post-job" className="font-medium text-cdtm hover:underline">
              post the first role
            </Link>{" "}
            for your company.
          </>
        }
        action={
          <ButtonLink href="/post-job" variant="primary">
            Post a job
          </ButtonLink>
        }
      />
    );
  }

  return (
    <div className="grid gap-8 md:grid-cols-[15rem_1fr] md:items-start">
      <aside className="hidden md:block md:sticky md:top-[4.5rem] md:rounded-xl md:border md:border-zinc-200 md:bg-white md:p-5">
        {filterPanel}
      </aside>

      <div>
        <header className="mb-6 space-y-4 border-b border-zinc-200 pb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-eyebrow">Open roles</p>
              <h1 className="font-display text-[2rem] font-medium leading-[1.12] tracking-[-0.025em] text-zinc-900 sm:text-[2.125rem]">
                Browse listings
              </h1>
              <p className="mt-2 max-w-2xl text-base leading-[1.65] text-zinc-600">
                Roles from CDTM partners and alumni-founded companies. Filter by arrangement,
                experience, and employment type.
              </p>
              <p className="mt-2 text-sm font-medium text-zinc-500">
                Showing {filtered.length} of {jobs.length}{" "}
                {jobs.length === 1 ? "listing" : "listings"}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <ButtonLink href="/jobs/alerts" variant="secondary">
                Job alerts
              </ButtonLink>
              <ButtonLink href="/post-job" variant="primary">
                Post a job
              </ButtonLink>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-800 md:hidden"
              onClick={() => setMobileFiltersOpen(true)}
            >
              Filters
              {activeFilterCount > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-cdtm px-1 text-xs font-semibold text-white">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <SearchField
              value={query}
              onChange={setQuery}
              placeholder="Search roles…"
              ariaLabel="Search roles"
            />
            <SortSelect
              value={sort}
              onChange={(v) => setSort(v as SortKey)}
              ariaLabel="Sort jobs"
              options={[
                { value: "newest", label: "Newest first" },
                { value: "oldest", label: "Oldest first" },
                { value: "company", label: "Company A-Z" },
                { value: "title", label: "Title A-Z" },
              ]}
            />
          </div>

          <FilterChips chips={chips} onClearAll={clearFilters} />
        </header>

        {filtered.length === 0 ? (
          <EmptyState
            title="No roles match your filters"
            description="Try removing a filter or changing your search terms."
            action={
              <button
                type="button"
                onClick={clearFilters}
                className="text-sm font-semibold text-cdtm hover:underline"
              >
                Clear filters
              </button>
            }
          />
        ) : (
          <ul className="overflow-hidden rounded-xl border border-zinc-200 bg-white" role="list">
            {filtered.map((job) => (
              <li key={job.id} className="border-b border-zinc-200 last:border-b-0">
                <JobRow
                  job={job}
                  companyName={companyById[job.company_id]?.name ?? null}
                  companyLogoUrl={companyById[job.company_id]?.logoUrl ?? null}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      <MobileFilterSheet open={mobileFiltersOpen} onClose={() => setMobileFiltersOpen(false)}>
        {filterPanel}
      </MobileFilterSheet>
    </div>
  );
}
