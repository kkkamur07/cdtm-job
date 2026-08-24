"use client";

import { ApiError } from "@/api/errors";
import { filterChips } from "./filters";
import { isNotReady } from "./useAsk";
import type { AnyInterpretation } from "./types";

/**
 * What the question was read as.
 *
 * The green rule down the left is the mock's way of saying "this part is the
 * machine talking". It shows three things and no more: the sentence the model
 * wrote back, the filters it actually applied, and the words it could not place.
 * Unresolved phrases are the honest half, so they are shown rather than dropped,
 * and `source: "rules"` is labelled, because a keyword fallback answers a
 * different question from the one that was asked.
 */
export default function AskAnalysis({
    interpretation,
    total,
    noun = "members",
    loading = false,
    error,
    question,
}: {
    interpretation?: AnyInterpretation | null;
    total?: number;
    noun?: string;
    loading?: boolean;
    error?: unknown;
    question: string;
}) {
    if (error) return <AskError error={error} />;

    if (loading && !interpretation) {
        return (
            <div className="analysis" role="status" aria-live="polite">
                <p className="atitle">Reading your question…</p>
                <p>Working out which filters “{question}” means.</p>
            </div>
        );
    }

    if (!interpretation) return null;

    const chips = filterChips(interpretation.filters);
    const unresolved = interpretation.unresolved ?? [];

    return (
        <div className="analysis" aria-live="polite">
            <p className="atitle">
                {typeof total === "number" ? (
                    <>
                        <b className="tabular-nums">{total}</b> {total === 1 ? noun.replace(/s$/, "") : noun}{" "}
                        {total === 1 ? "matches" : "match"}
                        {loading ? "…" : "."}
                    </>
                ) : (
                    "Interpreted."
                )}
            </p>
            <p>{interpretation.summary}</p>

            <div className="parsed">
                <span>Interpreted as</span>
                {chips.length > 0 ? (
                    chips.map((chip) => (
                        <span
                            key={chip.key}
                            className={`pill ${
                                chip.tone === "intent"
                                    ? "pill-intent"
                                    : chip.tone === "place"
                                      ? "pill-green"
                                      : "pill-outline"
                            }`}
                        >
                            {chip.label}
                        </span>
                    ))
                ) : (
                    <span className="pill pill-muted">everyone</span>
                )}

                {interpretation.source === "rules" && (
                    <span
                        className="pill pill-muted"
                        title="The model was not available, so the question was read by keyword."
                    >
                        Keyword mode
                    </span>
                )}
            </div>

            {unresolved.length > 0 && (
                <p className="parsed">
                    <span>Could not place</span>
                    {unresolved.map((phrase) => (
                        <span key={phrase} className="pill pill-muted">
                            {phrase}
                        </span>
                    ))}
                </p>
            )}
        </div>
    );
}

/**
 * Ask fails in three ways that mean different things to the reader, so they get
 * three different lines rather than one "something went wrong".
 */
function AskError({ error }: { error: unknown }) {
    if (isNotReady(error)) {
        return (
            <div className="analysis" role="status">
                <p className="atitle">Ask is warming up.</p>
                <p>
                    This backend does not answer plain-words questions yet. The filters below still
                    work, and Ask turns on here as soon as the endpoint ships.
                </p>
            </div>
        );
    }

    if (error instanceof ApiError && error.isRateLimited) {
        return (
            <div className="analysis" role="alert">
                <p className="atitle">Too many questions at once.</p>
                <p>Wait a few seconds and ask again. The filters below keep working meanwhile.</p>
            </div>
        );
    }

    if (error instanceof ApiError && error.isInvalid) {
        return (
            <div className="analysis" role="alert">
                <p className="atitle">That question could not be read.</p>
                <p>Ask in 3 to 300 characters, in plain words.</p>
            </div>
        );
    }

    return (
        <div className="analysis" role="alert">
            <p className="atitle">Ask did not answer.</p>
            <p>
                {error instanceof Error ? error.message : "Try the question again in a moment."} The
                filters below still work.
            </p>
        </div>
    );
}
