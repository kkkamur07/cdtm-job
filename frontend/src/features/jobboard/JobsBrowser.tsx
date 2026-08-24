"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import SearchIcon from "@/components/SearchIcon";
import { badgeLabel } from "@/lib/format";
import { useDebounced } from "@/lib/useDebounced";
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

/** Module scope: four closures rebuilt per render is four closures too many. */
const COMPARATORS: Record<SortKey, (a: JobRowData, b: JobRowData) => number> = {
    newest: (a, b) => b.postedAt.localeCompare(a.postedAt),
    oldest: (a, b) => a.postedAt.localeCompare(b.postedAt),
    company: (a, b) => a.company.localeCompare(b.company),
    title: (a, b) => a.title.localeCompare(b.title),
};

/**
 * The whole listing lives in memory.
 *
 * There are tens of roles, not thousands, so one request on the server beats a
 * round trip per checkbox: the counts next to each filter stay honest and the
 * list reorders in the same frame as the click. If the board ever outgrows a
 * hundred listings this moves back to the API's own query parameters.
 *
 * Every control ends up in the address bar. A filtered, sorted board is a
 * place: it has to survive a reload, come back with the back button, and be
 * sendable to somebody else. The checkboxes write there directly; the search
 * box types locally first and mirrors the settled value, because a place is
 * where the typing stopped, not each character on the way (see below).
 */
export default function JobsBrowser({ jobs, total }: { jobs: JobRowData[]; total: number }) {
    const { params, setParams } = useUrlState();

    const selection = useMemo(() => {
        const current = {} as Selection;
        for (const facet of FACETS) current[facet.key] = params.getAll(facet.param);
        return current;
    }, [params]);

    const question = params.get("ask") ?? "";
    const sortParam = params.get("sort");
    const sort: SortKey = sortParam && sortParam in SORTS ? (sortParam as SortKey) : "newest";

    /**
     * The search box types locally and mirrors to the URL afterwards.
     *
     * The URL is the right home for a settled search, because a filtered board
     * is a place. It is the wrong home for a half-typed one: `router.replace`
     * re-runs the route on the server, and reading the box's value back out of
     * the search params meant every character waited for that round trip and
     * visibly lagged. So the input renders from local state, the list filters
     * from a deferred copy of it, and the address bar catches up when the
     * typing stops.
     */
    const urlQuery = params.get("q") ?? "";
    const [typed, setTyped] = useState(urlQuery);
    const query = useDeferredValue(typed);
    const settled = useDebounced(typed, 300);
    // What we last wrote ourselves. Guarding on it means a URL that changed
    // some other way (the back button) is left alone rather than overwritten.
    const mirrored = useRef(urlQuery);

    useEffect(() => {
        if (settled === mirrored.current) return;
        mirrored.current = settled;
        setParams({ q: settled });
    }, [settled, setParams]);

    const setQuestion = (value: string) => setParams({ ask: value });
    const setSort = (value: SortKey) => setParams({ sort: value === "newest" ? null : value });
    const clearFacets = () =>
        setParams(Object.fromEntries(FACETS.map((facet) => [facet.param, null])));

    const clearEverything = useCallback(() => {
        // The box is local now, so clearing the URL is only half of it.
        setTyped("");
        mirrored.current = "";
        setParams({
            ...Object.fromEntries(FACETS.map((facet) => [facet.param, null])),
            q: null,
            ask: null,
        });
    }, [setParams]);

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

    // Filtering and sorting are separate memos: changing the sort should not
    // re-run the filter over the whole board.
    const filtered = useMemo(() => {
        const needle = query.trim().toLowerCase();
        return pool.filter((job) => {
            for (const { key } of FACETS) {
                const chosen = selection[key];
                if (chosen.length && !chosen.includes(job[key] ?? "")) return false;
            }
            if (!needle) return true;
            return `${job.title} ${job.company} ${job.location ?? ""}`.toLowerCase().includes(needle);
        });
    }, [pool, query, selection]);

    const shown = useMemo(() => filtered.toSorted(COMPARATORS[sort]), [filtered, sort]);

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
                            value={typed}
                            onChange={(event) => setTyped(event.target.value)}
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
                    /* The rows carry `cv-row`; the list itself must not, or the
                       browser skips the whole board rather than its off-screen
                       rows and the scrollbar jumps as it comes back. */
                    <ul className="card jlist">
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
                            onClick={clearEverything}
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
