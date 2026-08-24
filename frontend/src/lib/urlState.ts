"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

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
            router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
        },
        [params, pathname, router],
    );

    return { params, setParams };
}
