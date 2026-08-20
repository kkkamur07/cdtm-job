"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ClassRef, Member, Profile } from "@/lib/types";
import { getProfile, prefetchAll, preloadImage } from "@/lib/profiles";
import MemberTile from "./MemberTile";
import MemberModal from "./MemberModal";
import Toolbar, { type RoleFilter } from "./Toolbar";

const PAGE = 150;

/**
 * How many upcoming photos to warm on each keystroke. Two screenfuls, so the
 * bytes are already in flight before the tiles that need them mount. Higher
 * costs nothing extra in total — these are the same images the grid would
 * request anyway — it only moves the request earlier.
 */
const PRELOAD_COUNT = 48;

/**
 * Tiles rendered without lazy-loading. The lazy-load observer only fires once
 * a tile is near the viewport, which on a latent connection means the first
 * screenful starts its download late. These skip that wait entirely.
 */
const PRIORITY_COUNT = 12;

/** Lowercased haystack per member, built once. */
function haystack(m: Member): string {
    return [m.name, m.headline, m.company, m.title, m.major, m.classLabel, m.location]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
}

export default function MemberGrid({
                                       members,
                                       classes,
                                   }: {
    members: Member[];
    classes: ClassRef[];
}) {
    const router = useRouter();
    const pathname = usePathname();
    const params = useSearchParams();

    const [query, setQuery] = useState("");

    /**
     * NOT a debounce. useDeferredValue renders the list at lower priority, so
     * the input never stutters, but there is no fixed wall-clock wait — on a
     * responsive device it commits within a frame or two. A setTimeout here
     * would charge its full duration after every last keystroke, which is the
     * part you actually feel. Debouncing is for saving network requests; this
     * filter is in memory and takes under a millisecond.
     */
    const applied = useDeferredValue(query);
    const [classId, setClassId] = useState("all");
    const [role, setRole] = useState<RoleFilter>("all");
    const [limit, setLimit] = useState(PAGE);
    const [profile, setProfile] = useState<Profile | null>(null);
    const [pendingId, setPendingId] = useState<string | null>(null);

    const index = useMemo(
        () => members.map((m) => ({ member: m, text: haystack(m) })),
        [members]
    );

    const filterWith = useCallback(
        (q: string) => {
            const terms = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
            return index
                .filter(({ member, text }) => {
                    if (classId !== "all" && !member.classes.some((c) => String(c.id) === classId)) {
                        return false;
                    }
                    if (role === "student" && !member.roles.includes("student")) return false;
                    if (role === "ca" && !member.isCA) return false;
                    return terms.every((t) => text.includes(t));
                })
                .map(({ member }) => member);
        },
        [index, classId, role]
    );

    const filtered = useMemo(() => filterWith(applied), [filterWith, applied]);

    // Warm the photos for the pending query on the keystroke itself, so the
    // fetches are already in flight while React renders. This holds nothing
    // back — it just gives the network a head start of however long the render
    // takes.
    useEffect(() => {
        for (const m of filterWith(query).slice(0, PRELOAD_COUNT)) {
            if (m.avatar) preloadImage(m.avatar.sm, 0);
        }
    }, [query, filterWith]);

    useEffect(() => setLimit(PAGE), [applied, classId, role]);

    // Selection lives in the URL, so profiles are linkable and the browser back
    // button closes the modal — which people expect and otherwise complain about.
    const selectedId = params.get("member");

    // Load first, open second. Waiting for the JSON (and the portrait) before
    // touching the URL is what makes the panel appear in one piece instead of
    // a shell that fills in. Hover prefetching means the wait is usually zero.
    const open = useCallback(
        async (id: string) => {
            const member = members.find((m) => m.id === id);
            setPendingId(id);
            try {
                const [data] = await Promise.all([
                    getProfile(id),
                    preloadImage(member?.avatar?.lg),
                ]);

                // Deliberately NOT setProfile() here. The URL is the single trigger
                // for opening; setting state before the route updates made the sync
                // effect below fire while selectedId was still null, which closed the
                // modal one render after it opened. The data is cached by now, so the
                // effect resolves it in a microtask.
                void data;
                const next = new URLSearchParams(params.toString());
                next.set("member", id);
                router.push(`${pathname}?${next}`, { scroll: false });
            } catch {
                // Leave the modal closed rather than opening an empty one.
            } finally {
                setPendingId(null);
            }
        },
        [members, params, pathname, router]
    );

    // Covers deep links and back/forward, where nothing was prefetched.
    useEffect(() => {
        if (!selectedId) {
            setProfile(null);
            return;
        }
        let cancelled = false;
        getProfile(selectedId)
            .then((data) => !cancelled && setProfile(data))
            .catch(() => {});
        return () => {
            cancelled = true;
        };
        // selectedId ONLY. Including profile?.id here re-ran the effect on every
        // profile change and was what closed the modal on open.
    }, [selectedId]);

    const close = useCallback(() => {
        const next = new URLSearchParams(params.toString());
        next.delete("member");
        const qs = next.toString();
        router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    }, [params, pathname, router]);

    return (
        <>
            <Toolbar
                query={query}
                onQuery={setQuery}
                classId={classId}
                onClassId={setClassId}
                role={role}
                onRole={setRole}
                classes={classes}
                resultCount={filtered.length}
                totalCount={members.length}
            />

            <div className="shell pt-4 pb-24 sm:pt-6">
                {filtered.length === 0 ? (
                    <div className="py-24 text-center">
                        <p className="text-sm font-medium">No one matches those filters.</p>
                        <p className="mt-1 text-sm text-muted">
                            Try a shorter search, or widen the class filter.
                        </p>
                    </div>
                ) : (
                    <>
                        {/* Fixed column counts, not auto-fill. auto-fill derives columns
                from available width, so a wide window produced 7 tiny tiles.
                Explicit breakpoints cap the row at 4 and stay predictable
                under browser zoom, which changes the CSS-pixel viewport. */}
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4">
                            {filtered.slice(0, limit).map((m, i) => (
                                <MemberTile
                                    key={m.id}
                                    member={m}
                                    onOpen={open}
                                    onPrefetch={prefetchAll}
                                    busy={pendingId === m.id}
                                    priority={i < PRIORITY_COUNT}
                                />
                            ))}
                        </div>

                        {limit < filtered.length && (
                            <div className="mt-10 flex flex-col items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => setLimit((n) => n + PAGE)}
                                    className="h-10 rounded-[var(--radius-pill)] border border-line bg-white px-6 text-sm font-medium transition-colors hover:border-blue hover:text-blue"
                                >
                                    Show {Math.min(PAGE, filtered.length - limit).toLocaleString()} more
                                </button>
                                <p className="text-xs text-muted tabular-nums">
                                    Showing {limit.toLocaleString()} of {filtered.length.toLocaleString()}
                                </p>
                            </div>
                        )}
                    </>
                )}
            </div>

            <MemberModal profile={profile} onClose={close} />
        </>
    );
}