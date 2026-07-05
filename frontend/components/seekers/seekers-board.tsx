"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { SeekerListCard } from "@/components/seeker-list-card";
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
import { formatLabel, WORK_ARRANGEMENTS } from "@/lib/format-job";
import { toggleSetValue } from "@/lib/set-utils";
import type { SeekerPublic, WorkArrangement } from "@/lib/api/generated";

type SortKey = "newest" | "oldest" | "name";
type LinkFilter = "linkedin" | "github" | "portfolio";
type RemoteFilter = "open" | "not_open";
type ExperienceFilter = "entry" | "mid" | "senior";

type SeekersBoardProps = {
  seekers: SeekerPublic[];
};

const linkFilters: { key: LinkFilter; label: string }[] = [
  { key: "linkedin", label: "LinkedIn" },
  { key: "github", label: "GitHub" },
  { key: "portfolio", label: "Portfolio" },
];
const remoteFilters: { key: RemoteFilter; label: string }[] = [
  { key: "open", label: "Open to remote" },
  { key: "not_open", label: "On-site preferred" },
];
const experienceFilters: { key: ExperienceFilter; label: string }[] = [
  { key: "entry", label: "Up to 2 years" },
  { key: "mid", label: "3 to 5 years" },
  { key: "senior", label: "5+ years" },
];

function sortSeekers(seekers: SeekerPublic[], sort: SortKey) {
  const copy = [...seekers];
  copy.sort((a, b) => {
    if (sort === "newest") {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
    if (sort === "oldest") {
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    }
    return a.full_name.localeCompare(b.full_name);
  });
  return copy;
}

function topSkills(seekers: SeekerPublic[], limit = 10): string[] {
  const counts = new Map<string, number>();
  for (const s of seekers) {
    for (const skill of s.skills ?? []) {
      const key = skill.toLowerCase();
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([skill]) => skill);
}

function topLocations(seekers: SeekerPublic[], limit = 8): string[] {
  const counts = new Map<string, string>();
  for (const s of seekers) {
    for (const location of s.preferred_locations ?? []) {
      const key = location.trim().toLowerCase();
      if (!key) continue;
      if (!counts.has(key)) counts.set(key, location.trim());
    }
  }
  return [...counts.entries()]
    .sort((a, b) => a[1].localeCompare(b[1]))
    .slice(0, limit)
    .map(([, label]) => label);
}

function experienceBucket(years: number | null | undefined): ExperienceFilter | null {
  if (years == null) return null;
  if (years <= 2) return "entry";
  if (years <= 5) return "mid";
  return "senior";
}

function formatSkillLabel(skill: string): string {
  return skill.replace(/\b\w/g, (char) => char.toUpperCase());
}

function hasLink(seeker: SeekerPublic, link: LinkFilter): boolean {
  if (link === "linkedin") return !!seeker.linkedin_url;
  if (link === "github") return !!seeker.github_url;
  return !!seeker.portfolio_url;
}

export function SeekersBoard({ seekers }: SeekersBoardProps) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [arrangements, setArrangements] = useState<Set<WorkArrangement>>(new Set());
  const [remote, setRemote] = useState<Set<RemoteFilter>>(new Set());
  const [links, setLinks] = useState<Set<LinkFilter>>(new Set());
  const [skills, setSkills] = useState<Set<string>>(new Set());
  const [locations, setLocations] = useState<Set<string>>(new Set());
  const [experience, setExperience] = useState<Set<ExperienceFilter>>(new Set());
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const skillOptions = useMemo(() => topSkills(seekers), [seekers]);
  const locationOptions = useMemo(() => topLocations(seekers), [seekers]);

  const counts = useMemo(() => {
    const arrangement: Record<string, number> = {};
    const remoteCount: Record<string, number> = { open: 0, not_open: 0 };
    const linkCount: Record<string, number> = { linkedin: 0, github: 0, portfolio: 0 };
    const skillCount: Record<string, number> = {};
    const locationCount: Record<string, number> = {};
    const experienceCount: Record<string, number> = { entry: 0, mid: 0, senior: 0 };

    for (const s of seekers) {
      if (s.preferred_work_arrangement) {
        arrangement[s.preferred_work_arrangement] =
          (arrangement[s.preferred_work_arrangement] ?? 0) + 1;
      }
      if (s.open_to_remote === true) remoteCount.open += 1;
      if (s.open_to_remote === false) remoteCount.not_open += 1;
      if (s.linkedin_url) linkCount.linkedin += 1;
      if (s.github_url) linkCount.github += 1;
      if (s.portfolio_url) linkCount.portfolio += 1;
      const bucket = experienceBucket(s.years_of_experience);
      if (bucket) experienceCount[bucket] += 1;
      for (const skill of s.skills ?? []) {
        const key = skill.toLowerCase();
        skillCount[key] = (skillCount[key] ?? 0) + 1;
      }
      for (const location of s.preferred_locations ?? []) {
        const key = location.trim().toLowerCase();
        if (key) locationCount[key] = (locationCount[key] ?? 0) + 1;
      }
    }

    return { arrangement, remoteCount, linkCount, skillCount, locationCount, experienceCount };
  }, [seekers]);

  const filtered = useMemo(() => {
    let result = seekers;
    const q = query.trim().toLowerCase();

    if (q) {
      result = result.filter((s) => {
        const haystack = [
          s.full_name,
          s.headline,
          s.bio,
          ...(s.skills ?? []),
          ...(s.desired_role_titles ?? []),
          ...(s.preferred_locations ?? []),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(q);
      });
    }

    if (arrangements.size > 0) {
      result = result.filter(
        (s) => s.preferred_work_arrangement && arrangements.has(s.preferred_work_arrangement),
      );
    }

    if (remote.size > 0) {
      result = result.filter((s) => {
        if (remote.has("open") && s.open_to_remote === true) return true;
        if (remote.has("not_open") && s.open_to_remote === false) return true;
        return false;
      });
    }

    if (links.size > 0) {
      result = result.filter((s) => [...links].every((link) => hasLink(s, link)));
    }

    if (skills.size > 0) {
      result = result.filter((s) =>
        [...skills].every((skill) =>
          (s.skills ?? []).some((sSkill) => sSkill.toLowerCase() === skill),
        ),
      );
    }

    if (locations.size > 0) {
      result = result.filter((s) =>
        [...locations].some((location) =>
          (s.preferred_locations ?? []).some(
            (pref) => pref.trim().toLowerCase() === location,
          ),
        ),
      );
    }

    if (experience.size > 0) {
      result = result.filter((s) => {
        const bucket = experienceBucket(s.years_of_experience);
        return bucket != null && experience.has(bucket);
      });
    }

    return sortSeekers(result, sort);
  }, [seekers, query, arrangements, remote, links, skills, locations, experience, sort]);

  const activeFilterCount =
    arrangements.size + remote.size + links.size + skills.size + locations.size + experience.size;

  const toggle = <T,>(set: React.Dispatch<React.SetStateAction<Set<T>>>, value: T) => {
    set((prev) => toggleSetValue(prev, value));
  };

  const clearFilters = () => {
    setArrangements(new Set());
    setRemote(new Set());
    setLinks(new Set());
    setSkills(new Set());
    setLocations(new Set());
    setExperience(new Set());
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
      <FilterGroup title="Remote">
        {remoteFilters.map(({ key, label }) => (
          <FilterCheckbox
            key={key}
            label={label}
            count={counts.remoteCount[key] ?? 0}
            checked={remote.has(key)}
            onChange={() => toggle(setRemote, key)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Shared links">
        {linkFilters.map(({ key, label }) => (
          <FilterCheckbox
            key={key}
            label={label}
            count={counts.linkCount[key] ?? 0}
            checked={links.has(key)}
            onChange={() => toggle(setLinks, key)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Experience">
        {experienceFilters.map(({ key, label }) => (
          <FilterCheckbox
            key={key}
            label={label}
            count={counts.experienceCount[key] ?? 0}
            checked={experience.has(key)}
            onChange={() => toggle(setExperience, key)}
          />
        ))}
      </FilterGroup>
      {locationOptions.length > 0 && (
        <FilterGroup title="Preferred location">
          {locationOptions.map((location) => {
            const key = location.toLowerCase();
            return (
              <FilterCheckbox
                key={key}
                label={location}
                count={counts.locationCount[key] ?? 0}
                checked={locations.has(key)}
                onChange={() => toggle(setLocations, key)}
              />
            );
          })}
        </FilterGroup>
      )}
      {skillOptions.length > 0 && (
        <FilterGroup title="Skills">
          {skillOptions.map((skill) => (
            <FilterCheckbox
              key={skill}
              label={formatSkillLabel(skill)}
              count={counts.skillCount[skill] ?? 0}
              checked={skills.has(skill)}
              onChange={() => toggle(setSkills, skill)}
            />
          ))}
        </FilterGroup>
      )}
    </>
  );

  const chips: { id: string; label: string; clear: () => void }[] = [];
  arrangements.forEach((v) =>
    chips.push({ id: `arrangement:${v}`, label: formatLabel(v), clear: () => toggle(setArrangements, v) }),
  );
  remote.forEach((v) => {
    const label = remoteFilters.find((f) => f.key === v)?.label ?? v;
    chips.push({ id: `remote:${v}`, label, clear: () => toggle(setRemote, v) });
  });
  links.forEach((v) => {
    const label = linkFilters.find((f) => f.key === v)?.label ?? v;
    chips.push({ id: `link:${v}`, label, clear: () => toggle(setLinks, v) });
  });
  skills.forEach((v) =>
    chips.push({ id: `skill:${v}`, label: formatSkillLabel(v), clear: () => toggle(setSkills, v) }),
  );
  locations.forEach((v) => {
    const label = locationOptions.find((loc) => loc.toLowerCase() === v) ?? v;
    chips.push({ id: `location:${v}`, label, clear: () => toggle(setLocations, v) });
  });
  experience.forEach((v) => {
    const label = experienceFilters.find((f) => f.key === v)?.label ?? v;
    chips.push({ id: `experience:${v}`, label, clear: () => toggle(setExperience, v) });
  });

  if (seekers.length === 0) {
    return (
      <EmptyState
        title="No seeker profiles yet"
        description={
          <>
            Be the first to share your background with hiring teams.{" "}
            <Link href="/seekers/new" className="font-medium text-cdtm hover:underline">
              Create a profile
            </Link>
            .
          </>
        }
        action={
          <ButtonLink href="/seekers/new" variant="primary">
            Add your profile
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
              <p className="text-eyebrow">Directory</p>
              <h1 className="font-display text-[2rem] font-medium leading-[1.12] tracking-[-0.025em] text-zinc-900 sm:text-[2.125rem]">
                Discover great candidates
              </h1>
              <p className="mt-2 max-w-2xl text-base leading-[1.65] text-zinc-600">
                Profiles from the CDTM community. Filter by skills, location, experience, and links.
              </p>
              <p className="mt-2 text-sm font-medium text-zinc-500">
                Showing {filtered.length} of {seekers.length}{" "}
                {seekers.length === 1 ? "profile" : "profiles"}
              </p>
            </div>
            <ButtonLink href="/seekers/new" variant="primary" className="shrink-0">
              Add your profile
            </ButtonLink>
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
              placeholder="Search by name or skill…"
              ariaLabel="Search seekers"
            />
            <SortSelect
              value={sort}
              onChange={(v) => setSort(v as SortKey)}
              ariaLabel="Sort seekers"
              options={[
                { value: "newest", label: "Newest first" },
                { value: "oldest", label: "Oldest first" },
                { value: "name", label: "Name A-Z" },
              ]}
            />
          </div>

          <FilterChips chips={chips} onClearAll={clearFilters} />
        </header>

        {filtered.length === 0 ? (
          <EmptyState
            title="No profiles match your filters"
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
          <ul className="grid gap-3" role="list">
            {filtered.map((s) => (
              <SeekerListCard key={s.id} seeker={s} />
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
