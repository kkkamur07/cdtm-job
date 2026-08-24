"use client";

import { useCallback, useMemo, useState } from "react";

import { useUrlState } from "@/lib/urlState";
import AskAnalysis from "@/features/community/ask/AskAnalysis";
import AskLine from "@/features/community/ask/AskLine";
import { useHousingAsk } from "@/features/community/ask/useAsk";
import HousingCard, { type HousingCardData } from "./HousingCard";

const ASK_EXAMPLES = [
    "sublets in Berlin for two weeks",
    "who is looking in Munich",
    "a room under 900 from October",
];

const KINDS = [
    { key: "all", label: "All" },
    { key: "offer", label: "Offering" },
    { key: "looking", label: "Looking" },
] as const;

/**
 * Kind and city, filtered in the browser.
 *
 * Listings are counted in dozens, so holding them all is cheaper than a request
 * per chip, and the counts on the segmented control stay correct without a
 * second endpoint.
 *
 * The three controls write to the address bar, so a board narrowed to "rooms
 * offered in Munich" reloads, goes back and sends as what it looks like.
 */
export default function HousingBrowser({ listings }: { listings: HousingCardData[] }) {
    const { params, setParams } = useUrlState();
    const question = params.get("ask") ?? "";

    /**
     * The two filters are held locally and mirrored to the address bar.
     *
     * Both are answered entirely from `listings`, which is already in memory,
     * so the chip has no reason to wait for the URL: the local state repaints
     * the board in the same frame as the click, and the `replace` that follows
     * runs as a transition (`lib/urlState.ts`) so a slow round trip cannot hold
     * the next click.
     */
    const urlKind = params.get("kind") ?? "all";
    const urlCity = params.get("city") ?? "all";
    const [kind, setKindLocal] = useState(urlKind);
    const [city, setCityLocal] = useState(urlCity);

    /**
     * What this last wrote to the address bar, in the spirit of the `mirrored`
     * ref `JobsBrowser` keeps for its search box.
     *
     * The URL can also change without us: the back button, or a link into a
     * filtered board followed while this stays mounted. Without the guard the
     * chips would go on showing the filter the visitor just navigated away
     * from, and the board would be filtered by it. Adjusted during render
     * rather than from an effect, so no frame paints the stale filter.
     */
    const [mirrored, setMirrored] = useState({ kind: urlKind, city: urlCity });
    if (mirrored.kind !== urlKind || mirrored.city !== urlCity) {
        setMirrored({ kind: urlKind, city: urlCity });
        setKindLocal(urlKind);
        setCityLocal(urlCity);
    }

    const setKind = useCallback(
        (value: string) => {
            setMirrored((current) => ({ ...current, kind: value }));
            setKindLocal(value);
            setParams({ kind: value === "all" ? null : value });
        },
        [setParams],
    );

    const setCity = useCallback(
        (value: string) => {
            setMirrored((current) => ({ ...current, city: value }));
            setCityLocal(value);
            setParams({ city: value === "all" ? null : value });
        },
        [setParams],
    );

    const setQuestion = (value: string) => setParams({ ask: value });

    const answer = useHousingAsk(question, { enabled: question.length > 0 });

    // A question narrows the board rather than replacing it, so the segmented
    // control and the city chips keep working on top of the answer.
    const pool = useMemo(() => {
        const found = question ? answer.data?.listings : null;
        if (!found) return listings;
        const ids = new Set(found.map((listing) => listing.id));
        return listings.filter((listing) => ids.has(listing.id));
    }, [answer.data, listings, question]);

    const cities = useMemo(() => {
        const seen = new Map<string, number>();
        for (const listing of pool) {
            if (!listing.city) continue;
            seen.set(listing.city, (seen.get(listing.city) ?? 0) + 1);
        }
        return [...seen].sort((a, b) => b[1] - a[1]).map(([name]) => name);
    }, [pool]);

    // Both of these walked the whole pool on every keystroke in the ask box.
    // They only change when the pool or the two filters do.
    const shown = useMemo(
        () =>
            pool.filter(
                (listing) =>
                    (kind === "all" || listing.kind === kind) &&
                    (city === "all" || listing.city === city),
            ),
        [city, kind, pool],
    );

    const counts = useMemo(() => {
        const byKind = new Map<string, number>();
        for (const listing of pool) byKind.set(listing.kind, (byKind.get(listing.kind) ?? 0) + 1);
        return byKind;
    }, [pool]);

    const countOf = (key: string) => (key === "all" ? pool.length : (counts.get(key) ?? 0));

    return (
        <>
            <AskLine
                placeholder="room in Schwabing under 900 from October…"
                examples={ASK_EXAMPLES}
                value={question}
                busy={answer.isFetching}
                onAsk={setQuestion}
                onClear={() => setQuestion("")}
            >
                {question && (
                    <AskAnalysis
                        question={question}
                        noun="listings"
                        interpretation={answer.data?.interpretation}
                        total={answer.data?.total}
                        loading={answer.isFetching}
                        error={answer.error}
                    />
                )}
            </AskLine>

            <div className="mb-5 flex flex-wrap items-center gap-2.5">
                <div className="segment" role="group" aria-label="Listing kind">
                    {KINDS.map((option) => (
                        <button
                            key={option.key}
                            type="button"
                            aria-pressed={kind === option.key}
                            onClick={() => setKind(option.key)}
                        >
                            {option.label}
                            <span className="tabular-nums opacity-70">{countOf(option.key)}</span>
                        </button>
                    ))}
                </div>

                {cities.length > 1 && (
                    <>
                        <select
                            className="select w-auto min-w-[150px]"
                            aria-label="City"
                            value={city}
                            onChange={(event) => setCity(event.target.value)}
                        >
                            <option value="all">All cities</option>
                            {cities.map((name) => (
                                <option key={name} value={name}>
                                    {name}
                                </option>
                            ))}
                        </select>

                        <div className="chips">
                            {cities.slice(0, 5).map((name) => (
                                <button
                                    key={name}
                                    type="button"
                                    className="chip"
                                    aria-pressed={city === name}
                                    onClick={() => setCity(city === name ? "all" : name)}
                                >
                                    {name}
                                </button>
                            ))}
                        </div>
                    </>
                )}

                <p className="ml-auto text-[13px] text-muted" aria-live="polite">
                    {question ? "Your question matches " : "Showing "}
                    <b className="tabular-nums text-ink">{shown.length}</b> of {listings.length}
                </p>
            </div>

            {/* The page's h1 is above this, and each card heads itself with an
                h3, so the list needs an h2 of its own to sit under. */}
            <h2 className="sr-only">Listings</h2>

            {shown.length ? (
                /* The cards carry `cv-card` themselves; the grid must not, or
                   the browser skips the whole board rather than its off-screen
                   rows. */
                <div className="hgrid three">
                    {shown.map((listing, index) => (
                        <HousingCard key={listing.id} listing={listing} index={index} />
                    ))}
                </div>
            ) : (
                <div className="card px-4 py-10 text-center text-[13.5px] text-muted">
                    {question
                        ? "Nothing matches that question yet."
                        : "No listings match. Post one, it takes a minute."}
                </div>
            )}
        </>
    );
}
