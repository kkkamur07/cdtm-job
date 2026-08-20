"use client";

import { useMemo, useState } from "react";

import { CompanyCard } from "@/components/companies/company-card";
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
import type { CompanyBoardItem } from "@/lib/format-company";
import { toggleSetValue } from "@/lib/set-utils";

type SortKey = "name" | "roles_desc" | "roles_asc";

type CompaniesBoardProps = {
  companies: CompanyBoardItem[];
};

function hqCity(hq: string): string {
  return hq.split(",")[0]?.trim() ?? hq;
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function sortCompanies(companies: CompanyBoardItem[], sort: SortKey): CompanyBoardItem[] {
  const copy = [...companies];
  copy.sort((a, b) => {
    if (sort === "roles_desc") {
      return b.openRoles.length - a.openRoles.length || a.name.localeCompare(b.name);
    }
    if (sort === "roles_asc") {
      return a.openRoles.length - b.openRoles.length || a.name.localeCompare(b.name);
    }
    return a.name.localeCompare(b.name);
  });
  return copy;
}

export function CompaniesBoard({ companies }: CompaniesBoardProps) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [industries, setIndustries] = useState<Set<string>>(new Set());
  const [sizes, setSizes] = useState<Set<string>>(new Set());
  const [locations, setLocations] = useState<Set<string>>(new Set());
  const [cdtmOnly, setCdtmOnly] = useState(false);
  const [hiringOnly, setHiringOnly] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const industryOptions = useMemo(
    () => uniqueSorted(companies.map((c) => c.industry).filter((v): v is string => Boolean(v))),
    [companies],
  );
  const sizeOptions = useMemo(
    () => uniqueSorted(companies.map((c) => c.companySizeLabel)),
    [companies],
  );
  const locationOptions = useMemo(
    () => uniqueSorted(companies.map((c) => hqCity(c.hqLabel))),
    [companies],
  );

  const counts = useMemo(() => {
    const industry: Record<string, number> = {};
    const size: Record<string, number> = {};
    const location: Record<string, number> = {};
    let cdtm = 0;
    let hiring = 0;

    for (const c of companies) {
      if (c.industry) industry[c.industry] = (industry[c.industry] ?? 0) + 1;
      size[c.companySizeLabel] = (size[c.companySizeLabel] ?? 0) + 1;
      const city = hqCity(c.hqLabel);
      location[city] = (location[city] ?? 0) + 1;
      if (c.is_cdtm_startup) cdtm += 1;
      if (c.openRoles.length > 0) hiring += 1;
    }

    return { industry, size, location, cdtm, hiring };
  }, [companies]);

  const filtered = useMemo(() => {
    let result = companies;
    const q = query.trim().toLowerCase();

    if (q) {
      result = result.filter((c) => {
        const haystack = [c.name, c.short_description, c.industry, c.hqLabel, c.companySizeLabel]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(q);
      });
    }

    if (industries.size > 0) {
      result = result.filter((c) => c.industry != null && industries.has(c.industry));
    }

    if (sizes.size > 0) {
      result = result.filter((c) => sizes.has(c.companySizeLabel));
    }

    if (locations.size > 0) {
      result = result.filter((c) => locations.has(hqCity(c.hqLabel)));
    }

    if (cdtmOnly) {
      result = result.filter((c) => c.is_cdtm_startup);
    }

    if (hiringOnly) {
      result = result.filter((c) => c.openRoles.length > 0);
    }

    return sortCompanies(result, sort);
  }, [companies, query, industries, sizes, locations, cdtmOnly, hiringOnly, sort]);

  const activeFilterCount =
    industries.size + sizes.size + locations.size + (cdtmOnly ? 1 : 0) + (hiringOnly ? 1 : 0);

  const toggle = <T,>(set: React.Dispatch<React.SetStateAction<Set<T>>>, value: T) => {
    set((prev) => toggleSetValue(prev, value));
  };

  const clearFilters = () => {
    setIndustries(new Set());
    setSizes(new Set());
    setLocations(new Set());
    setCdtmOnly(false);
    setHiringOnly(false);
    setQuery("");
  };

  const filterPanel = (
    <>
      <FilterPanelHead activeCount={activeFilterCount} onClear={clearFilters} />
      <FilterGroup title="Industry">
        {industryOptions.map((value) => (
          <FilterCheckbox
            key={value}
            label={value}
            count={counts.industry[value] ?? 0}
            checked={industries.has(value)}
            onChange={() => toggle(setIndustries, value)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Company size">
        {sizeOptions.map((value) => (
          <FilterCheckbox
            key={value}
            label={value}
            count={counts.size[value] ?? 0}
            checked={sizes.has(value)}
            onChange={() => toggle(setSizes, value)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Headquarters">
        {locationOptions.map((value) => (
          <FilterCheckbox
            key={value}
            label={value}
            count={counts.location[value] ?? 0}
            checked={locations.has(value)}
            onChange={() => toggle(setLocations, value)}
          />
        ))}
      </FilterGroup>
      <FilterGroup title="Highlights">
        <FilterCheckbox
          label="CDTM startup"
          count={counts.cdtm}
          checked={cdtmOnly}
          onChange={() => setCdtmOnly((v) => !v)}
        />
        <FilterCheckbox
          label="Hiring now"
          count={counts.hiring}
          checked={hiringOnly}
          onChange={() => setHiringOnly((v) => !v)}
        />
      </FilterGroup>
    </>
  );

  const chips: { id: string; label: string; clear: () => void }[] = [];
  industries.forEach((v) =>
    chips.push({ id: `industry:${v}`, label: v, clear: () => toggle(setIndustries, v) }),
  );
  sizes.forEach((v) => chips.push({ id: `size:${v}`, label: v, clear: () => toggle(setSizes, v) }));
  locations.forEach((v) =>
    chips.push({ id: `location:${v}`, label: v, clear: () => toggle(setLocations, v) }),
  );
  if (cdtmOnly) chips.push({ id: "cdtm", label: "CDTM startup", clear: () => setCdtmOnly(false) });
  if (hiringOnly) chips.push({ id: "hiring", label: "Hiring now", clear: () => setHiringOnly(false) });

  if (companies.length === 0) {
    return (
      <EmptyState
        title="No companies yet"
        description="Company profiles will appear here once they join the board."
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
          <div>
            <p className="text-eyebrow">Directory</p>
            <h1 className="font-display text-[2rem] font-medium leading-[1.12] tracking-[-0.025em] text-zinc-900 sm:text-[2.125rem]">
              Companies
            </h1>
            <p className="mt-2 max-w-2xl text-base leading-[1.65] text-zinc-600">
              Explore teams hiring CDTM talent — profiles and open roles from the live board.
            </p>
            <p className="mt-2 text-sm font-medium text-zinc-500">
              Showing {filtered.length} of {companies.length}{" "}
              {companies.length === 1 ? "company" : "companies"}
            </p>
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
              placeholder="Search companies…"
              ariaLabel="Search companies"
            />
            <SortSelect
              value={sort}
              onChange={(v) => setSort(v as SortKey)}
              ariaLabel="Sort companies"
              options={[
                { value: "name", label: "Name A-Z" },
                { value: "roles_desc", label: "Most open roles" },
                { value: "roles_asc", label: "Fewest open roles" },
              ]}
            />
          </div>

          <FilterChips chips={chips} onClearAll={clearFilters} />
        </header>

        {filtered.length === 0 ? (
          <EmptyState
            title="No companies match your filters"
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
          <ul className="grid gap-3 sm:grid-cols-2 sm:items-stretch" role="list">
            {filtered.map((company) => (
              <li key={company.slug} className="h-full min-h-0">
                <CompanyCard company={company} />
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
