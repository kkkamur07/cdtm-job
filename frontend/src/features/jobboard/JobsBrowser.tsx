"use client";

import { useMemo } from "react";

import SearchIcon from "@/components/SearchIcon";
import { badgeLabel } from "@/lib/format";
import { useUrlState } from "@/lib/urlState";
import AskAnalysis from "@/features/community/ask/AskAnalysis";
import AskLine from "@/features/community/ask/AskLine";
import { useJobAsk } from "@/features/community/ask/useAsk";
import JobRow from "./JobRow";
import type { JobRowData } from "./jobData";

const ASK_EXAMPLES = [
    "working student roles in Berlin that sponsor visas",
    "who is hiring engineers in Paris",
    "roles where a CDTM person is the poster",
];

type FacetKey = "employmentType" | "workArrangement" | "experienceLevel" | "city";
type Selection = Record<FacetKey, string[]>;

/** `param` is what the facet is called in the URL: short, and stable. */
const FACETS: { key: FacetKey; title: string; param: string }[] = [
    { key: "employmentType", title: "Type", param: "type" },
    { key: "workArrangement", title: "Arrangement", param: "work" },
    { key: "experienceLevel", title: "Level", param: "level" },
    { key: "city", title: "City", param: "city" },
];

const SORTS = {
    newest: "Newest first",
    oldest: "Oldest first",
    company: "Company A to Z",
    title: "Title A to Z",
} as const;
type SortKey = keyof typeof SORTS;

/**
 * The whole listing lives in memory.
 *
 * There are tens of roles, not thousands, so one request on the server beats a
 * round trip per checkbox: the counts next to each filter stay honest and the
 * list reorders in the same frame as the click. If the board ever outgrows a
 * hundred listings this moves back to the API's own query parameters.
 *
 * Every control writes to the address bar rather than to local state. A
 * filtered, sorted board is a place: it has to survive a reload, come back with
 * the back button, and be sendable to somebody else.
 */
export default function JobsBrowser({ jobs, total }: { jobs: JobRowData[]; total: number }) {
    const { params, setParams } = useUrlState();

    const selection = useMemo(() => {
        const current = {} as Selection;
        for (const facet of FACETS) current[facet.key] = params.getAll(facet.param);
        return current;
    }, [params]);

    const query = params.get("q") ?? "";
    const question = params.get("ask") ?? "";
    const sortParam = params.get("sort");
    const sort: SortKey = sortParam && sortParam in SORTS ? (sortParam as SortKey) : "newest";

    const setQuery = (value: string) => setParams({ q: value });
    const setQuestion = (value: string) => setParams({ ask: value });
    const setSort = (value: SortKey) => setParams({ sort: value === "newest" ? null : value });
    const clearFacets = () =>
        setParams(Object.fromEntries(FACETS.map((facet) => [facet.param, null])));

    const answer = useJobAsk(question, { enabled: question.length > 0 });

    /**
     * An answer narrows the board rather than replacing it.
     *
     * Ask returns whole jobs; the rows here already carry the company and the
     * poster, resolved once on the server. Intersecting by id keeps one shape
     * of row on the page and means the checkboxes and the question compose:
     * ask for Berlin, then tick "Remote", and both apply.
     */
    const askedIds = useMemo(() => {
        if (!question || !answer.data?.jobs) return null;
        return new Set(answer.data.jobs.map((job) => job.id));
    }, [answer.data, question]);

    const pool = useMemo(
        () => (askedIds ? jobs.filter((job) => askedIds.has(job.id)) : jobs),
        [askedIds, jobs],
    );

    const counts = useMemo(() => {
        const result = {} as Record<FacetKey, Map<string, number>>;
        for (const { key } of FACETS) {
            const map = new Map<string, number>();
            for (const job of pool) {
                const value = job[key];
                if (!value) continue;
                map.set(value, (map.get(value) ?? 0) + 1);
            }
            result[key] = new Map([...map].sort((a, b) => b[1] - a[1]));
        }
        return result;
    }, [pool]);

    const shown = useMemo(() => {
        const needle = query.trim().toLowerCase();
        const filtered = pool.filter((job) => {
            for (const { key } of FACETS) {
                const chosen = selection[key];
                if (chosen.length && !chosen.includes(job[key] ?? "")) return false;
            }
            if (!needle) return true;
            return `${job.title} ${job.company} ${job.location ?? ""}`.toLowerCase().includes(needle);
        });

        const by: Record<SortKey, (a: JobRowData, b: JobRowData) => number> = {
            newest: (a, b) => b.postedAt.localeCompare(a.postedAt),
            oldest: (a, b) => a.postedAt.localeCompare(b.postedAt),
            company: (a, b) => a.company.localeCompare(b.company),
            title: (a, b) => a.title.localeCompare(b.title),
        };
        return [...filtered].sort(by[sort]);
    }, [pool, query, selection, sort]);

    const activeCount = Object.values(selection).reduce((sum, list) => sum + list.length, 0);

    const toggle = (key: FacetKey, value: string) => {
        const facet = FACETS.find((item) => item.key === key);
        if (!facet) return;
        const chosen = selection[key];
        setParams({
            [facet.param]: chosen.includes(value)
                ? chosen.filter((item) => item !== value)
                : [...chosen, value],
        });
    };

    return (
        <>
            <AskLine
                placeholder="remote product roles at CDTM startups…"
                examples={ASK_EXAMPLES}
                value={question}
                busy={answer.isFetching}
                onAsk={setQuestion}
                onClear={() => setQuestion("")}
            >
                {question && (
                    <AskAnalysis
                        question={question}
                        noun="roles"
                        interpretation={answer.data?.interpretation}
                        total={answer.data?.total}
                        loading={answer.isFetching}
                        error={answer.error}
                    />
                )}
            </AskLine>

            <div className="board">
            <aside className="card frail">
                <div className="frail-h">
                    {/* An h2 under the page's h1, so the facet headings below
                        are h3s that follow it rather than a jumped rank. */}
                    <h2>Filters</h2>
                    {activeCount > 0 && (
                        <button
                            type="button"
                            className="text-[12px] font-medium text-blue"
                            onClick={clearFacets}
                        >
                            Clear all
                        </button>
                    )}
                </div>

                {FACETS.map((facet) => {
                    const values = [...counts[facet.key]];
                    if (!values.length) return null;
                    return (
                        <fieldset key={facet.key} className="fgroup">
                            <legend className="sr-only">{facet.title}</legend>
                            <h3 aria-hidden="true">{facet.title}</h3>
                            {values.slice(0, 8).map(([value, count]) => {
                                const on = selection[facet.key].includes(value);
                                return (
                                    <label key={value} className={`fopt ${on ? "on" : ""}`}>
                                        <span className="flex items-center">
                                            <input
                                                type="checkbox"
                                                checked={on}
                                                onChange={() => toggle(facet.key, value)}
                                            />
                                            <span>{badgeLabel(value)}</span>
                                        </span>
                                        <span className="n">{count}</span>
                                    </label>
                                );
                            })}
                        </fieldset>
                    );
                })}
            </aside>

            <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 pb-4">
                    <div className="search">
                        <SearchIcon />
                        <input
                            type="search"
                            placeholder="Search roles"
                            aria-label="Search roles"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                        />
                    </div>
                    <select
                        className="select w-auto"
                        aria-label="Sort jobs"
                        value={sort}
                        onChange={(event) => setSort(event.target.value as SortKey)}
                    >
                        {Object.entries(SORTS).map(([value, label]) => (
                            <option key={value} value={value}>
                                {label}
                            </option>
                        ))}
                    </select>
                </div>

                {activeCount > 0 && (
                    <div className="chips pb-4">
                        {FACETS.flatMap((facet) =>
                            selection[facet.key].map((value) => (
                                <button
                                    key={`${facet.key}-${value}`}
                                    type="button"
                                    className="chip"
                                    aria-pressed="true"
                                    onClick={() => toggle(facet.key, value)}
                                >
                                    {badgeLabel(value)} <span aria-hidden="true">×</span>
                                    <span className="sr-only">Remove filter</span>
                                </button>
                            )),
                        )}
                        <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={clearFacets}
                        >
                            Clear all
                        </button>
                    </div>
                )}

                <p className="count pb-3 text-[12.5px] text-muted" aria-live="polite">
                    {question ? "Your question matches " : "Showing "}
                    <b className="tabular-nums text-ink">{shown.length}</b> of {total}{" "}
                    {total === 1 ? "listing" : "listings"}
                </p>

                <h2 className="sr-only">Roles</h2>

                {shown.length ? (
                    <ul className="card jlist [content-visibility:auto]">
                        {shown.map((job) => (
                            <JobRow key={job.id} job={job} />
                        ))}
                    </ul>
                ) : (
                    <div className="card px-4 py-10 text-center text-[13.5px] text-muted">
                        No roles match{question ? " your question and filters" : " your filters"}.{" "}
                        <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() =>
                                setParams({
                                    ...Object.fromEntries(
                                        FACETS.map((facet) => [facet.param, null]),
                                    ),
                                    q: null,
                                    ask: null,
                                })
                            }
                        >
                            Clear everything
                        </button>
                    </div>
                )}
            </div>
            </div>
        </>
    );
}
