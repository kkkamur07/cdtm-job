"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { startTransition, useCallback } from "react";

/**
 * Screen state that belongs in the address bar.
 *
 * A filtered board, a sorted list or an open tab is a place, not a mood: it
 * should survive a reload, come back with the back button, and be sendable to
 * somebody. `router.replace` rather than `push`, so ticking six filters does
 * not bury the previous page under six history entries, and `scroll: false`,
 * so the list does not jump to the top every time a checkbox moves.
 *
 * Empty and null values drop the key entirely, which keeps the default state
 * at a clean URL instead of one carrying `?sort=newest&q=`.
 *
 * The write is a transition. A `replace` on an app-router URL re-runs the
 * server component for that route, and without a transition React treats that
 * as urgent work: the click that ticked the checkbox is held until the payload
 * comes back. Inside one, the tick paints immediately and the new URL arrives
 * when it arrives.
 */
export function useUrlState() {
    const router = useRouter();
    const pathname = usePathname();
    const params = useSearchParams();

    const setParams = useCallback(
        (changes: Record<string, string | string[] | null | undefined>) => {
            const next = new URLSearchParams(params.toString());
            for (const [key, value] of Object.entries(changes)) {
                next.delete(key);
                if (value === null || value === undefined || value === "") continue;
                if (Array.isArray(value)) {
                    for (const item of value) if (item) next.append(key, item);
                } else {
                    next.set(key, value);
                }
            }
            const query = next.toString();
            startTransition(() => {
                router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
            });
        },
        [params, pathname, router],
    );

    return { params, setParams };
}
