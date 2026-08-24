"use client";

import { errorMessage } from "@/api/errors";

/**
 * The two states that need a client: something failed, and here is what to do
 * about it. `ErrorState` takes a retry callback, which only a client component
 * can hand it.
 *
 * The loading skeleton and the empty state are pure markup and live in
 * `placeholders.tsx`, so a server component can draw them without pulling this
 * module into the browser bundle.
 */

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
    return (
        <div role="alert" className="grid justify-items-center gap-2 px-4 py-9 text-center">
            <p className="text-sm font-medium">That did not load.</p>
            <p className="max-w-[46ch] text-[13px] text-muted">{errorMessage(error)}</p>
            {onRetry && (
                <button type="button" className="btn btn-sm mt-1" onClick={onRetry}>
                    Try again
                </button>
            )}
        </div>
    );
}

/** Inline form-level error, styled to sit inside a card rather than replace it. */
export function FormError({ error }: { error: unknown }) {
    if (!error) return null;
    return (
        <p
            role="alert"
            className="rounded-2xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13px] text-red-800"
        >
            {errorMessage(error)}
        </p>
    );
}
