import type { Profile } from "./types";

/**
 * Profile loading, shared across the grid and the modal.
 *
 * The modal used to open on click and fetch afterwards, so on a slow
 * connection you saw the shell appear and the body fill in a moment later.
 * Now the grid waits for the data before opening, and warms the cache on
 * hover so that wait is usually already over by the time you click.
 */

const cache = new Map<string, Profile>();
const inflight = new Map<string, Promise<Profile>>();

export function getProfile(id: string): Promise<Profile> {
    const hit = cache.get(id);
    if (hit) return Promise.resolve(hit);

    // Dedupe: hovering then clicking must not fire two requests.
    const pending = inflight.get(id);
    if (pending) return pending;

    const request = fetch(`/profiles/${id}.json`)
        .then((r) => {
            if (!r.ok) throw new Error(`profile ${id}: HTTP ${r.status}`);
            return r.json() as Promise<Profile>;
        })
        .then((data) => {
            cache.set(id, data);
            inflight.delete(id);
            return data;
        })
        .catch((err) => {
            inflight.delete(id);
            throw err;
        });

    inflight.set(id, request);
    return request;
}

/** Fire and forget — used on hover and focus. Failures are irrelevant here. */
export function prefetchProfile(id: string): void {
    void getProfile(id).catch(() => {});
}

/**
 * Decode the modal-sized avatar before opening, so the portrait doesn't pop in
 * a frame late. Capped: a slow image should delay the modal by a little, never
 * hold it hostage.
 */
export function preloadImage(src: string | null | undefined, budgetMs = 250): Promise<void> {
    if (!src) return Promise.resolve();

    const img = new Image();
    img.src = src;

    const decoded = img.decode().catch(() => {});
    const budget = new Promise<void>((resolve) => setTimeout(resolve, budgetMs));
    return Promise.race([decoded, budget]) as Promise<void>;
}

/** Warm both the JSON and the large portrait. */
export function prefetchAll(id: string, avatarLg?: string | null): void {
    prefetchProfile(id);
    if (avatarLg) preloadImage(avatarLg, 0);
}