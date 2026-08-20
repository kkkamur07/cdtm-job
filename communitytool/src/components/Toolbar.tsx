"use client";

import { useEffect, useState } from "react";
import type { ClassRef } from "@/lib/types";

export type RoleFilter = "all" | "student" | "ca";

const ROLES: { value: RoleFilter; label: string }[] = [
    { value: "all", label: "Everyone" },
    { value: "student", label: "Students" },
    { value: "ca", label: "CAs" },
];

/**
 * Presentational. Spans the full viewport so the sticky bar reads as a real
 * chrome edge, with its own inner container matching the content column.
 *
 * Layout is three explicit groups — search / filters / status — that sit on
 * one row from `sm` up and stack on phones. It is NOT flex-wrap: wrapping let
 * the browser decide the break points, which put a lone control on its own
 * line at some widths and produced the ragged mobile layout.
 *
 * Two rules keep the row from jittering as you type:
 *
 *  - Search is the only flex item. Everything else is a fixed width, so the
 *    field never resizes when the count string changes length.
 *  - The reset button occupies its slot at all times and only toggles
 *    visibility, so nothing reflows when filters come and go.
 *
 * There is deliberately no row of filter chips. They restated what the three
 * controls already showed, and appearing on the first keystroke pushed the
 * whole grid down.
 */
export default function Toolbar({
                                    query,
                                    onQuery,
                                    classId,
                                    onClassId,
                                    role,
                                    onRole,
                                    classes,
                                    resultCount,
                                    totalCount,
                                }: {
    query: string;
    onQuery: (v: string) => void;
    classId: string;
    onClassId: (v: string) => void;
    role: RoleFilter;
    onRole: (v: RoleFilter) => void;
    classes: ClassRef[];
    resultCount: number;
    totalCount: number;
}) {
    // The border only appears once the bar has something to separate itself
    // from — flat against the masthead, edged once content scrolls under it.
    const [stuck, setStuck] = useState(false);
    useEffect(() => {
        const onScroll = () => setStuck(window.scrollY > 8);
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    const filtered = query.trim() !== "" || classId !== "all" || role !== "all";

    const reset = () => {
        onQuery("");
        onClassId("all");
        onRole("all");
    };

    return (
        <div
            className={`sticky top-0 z-20 bg-cream/90 backdrop-blur-md transition-shadow duration-200 ${
                stuck
                    ? "border-b border-line shadow-[0_1px_12px_rgb(26_26_26/0.04)]"
                    : "border-b border-transparent"
            }`}
        >
            <div className="shell py-2.5 sm:py-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    {/* Search — the only element allowed to flex. */}
                    <div className="relative w-full sm:min-w-0 sm:flex-1">
                        <svg
                            className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted"
                            width="15"
                            height="15"
                            viewBox="0 0 16 16"
                            fill="none"
                            aria-hidden="true"
                        >
                            <circle cx="7" cy="7" r="4.75" stroke="currentColor" strokeWidth="1.5" />
                            <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                        <input
                            type="search"
                            value={query}
                            onChange={(e) => onQuery(e.target.value)}
                            placeholder="Search name, company, or major"
                            aria-label="Search members"
                            className="h-10 w-full rounded-[var(--radius-pill)] border border-line bg-white pr-9 pl-10 text-sm transition-colors placeholder:text-muted focus:border-blue focus:outline-none [&::-webkit-search-cancel-button]:hidden"
                        />
                        {query && (
                            <button
                                type="button"
                                onClick={() => onQuery("")}
                                aria-label="Clear search"
                                className="absolute top-1/2 right-2.5 -translate-y-1/2 rounded-full p-1 text-muted transition-colors hover:bg-cream hover:text-ink"
                            >
                                <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true">
                                    <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                                </svg>
                            </button>
                        )}
                    </div>

                    {/* Filters — share a row on phones, fixed widths from sm up. */}
                    <div className="flex items-center gap-2">
                        <div className="relative min-w-0 flex-1 sm:w-32 sm:flex-none">
                            <select
                                value={classId}
                                onChange={(e) => onClassId(e.target.value)}
                                aria-label="Filter by class"
                                className={`h-10 w-full appearance-none rounded-[var(--radius-pill)] border bg-white pr-8 pl-3.5 text-sm transition-colors focus:outline-none ${
                                    classId === "all" ? "border-line" : "border-blue text-blue"
                                }`}
                            >
                                <option value="all">All classes</option>
                                {classes.map((c) => (
                                    <option key={c.id} value={c.id}>
                                        {c.label}
                                    </option>
                                ))}
                            </select>
                            <svg
                                className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-muted"
                                width="10"
                                height="10"
                                viewBox="0 0 12 12"
                                aria-hidden="true"
                            >
                                <path d="M2 4.5L6 8.5L10 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" fill="none" />
                            </svg>
                        </div>

                        <div className="flex h-10 shrink-0 items-center gap-0.5 rounded-[var(--radius-pill)] border border-line bg-white p-1">
                            {ROLES.map((r) => (
                                <button
                                    key={r.value}
                                    type="button"
                                    onClick={() => onRole(r.value)}
                                    aria-pressed={role === r.value}
                                    className={`h-8 rounded-[var(--radius-pill)] px-2.5 text-[13px] font-medium transition-colors sm:px-3 ${
                                        role === r.value
                                            ? "bg-blue text-white"
                                            : "text-muted hover:bg-cream hover:text-ink"
                                    }`}
                                >
                                    {r.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Status — count and reset. On phones this is a short text row
              rather than a third bank of 40px controls. */}
                    <div className="flex items-center justify-between gap-3 sm:shrink-0 sm:justify-end">
                        <p
                            aria-live="polite"
                            className="text-[13px] whitespace-nowrap text-muted tabular-nums sm:w-24 sm:text-right"
                        >
                            {filtered ? (
                                <>
                                    <span className="font-semibold text-ink">{resultCount.toLocaleString()}</span>
                                    {" of "}
                                    {totalCount.toLocaleString()}
                                </>
                            ) : (
                                <>
                                    <span className="font-semibold text-ink">{totalCount.toLocaleString()}</span>
                                    {" members"}
                                </>
                            )}
                        </p>

                        {/* Always occupies its slot; only visibility changes. */}
                        <button
                            type="button"
                            onClick={reset}
                            tabIndex={filtered ? 0 : -1}
                            aria-hidden={!filtered}
                            className={`shrink-0 text-[13px] font-medium text-blue transition-opacity hover:opacity-70 ${
                                filtered ? "" : "pointer-events-none invisible"
                            }`}
                        >
                            Reset
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}