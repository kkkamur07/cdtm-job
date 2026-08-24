"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "../client";
import { qk } from "../keys";
import type {
    DirectoryFacets,
    EntryUpsert,
    IntentsUpsert,
    IntroRequestsPage,
    IntroStatus,
    Me,
    MemberProfile,
    NetworkMember,
    SavedMemberIds,
    SavedMembersPage,
    SelfProfileCreate,
} from "../types";
import { useAuthedQueryOptions } from "./shared";

/** The classes and majors a new profile picks from. Needs a session (member-only route). */
export function useFacets() {
    const gate = useAuthedQueryOptions();
    return useQuery<DirectoryFacets>({
        queryKey: qk.memberFacets,
        queryFn: () => unwrap(api.GET("/api/v1/members/facets", {})),
        ...gate,
    });
}

/** Claim a member profile for a signed-in account that no roster row matched. */
export function useCreateMyProfile() {
    const qc = useQueryClient();
    return useMutation<MemberProfile, Error, SelfProfileCreate>({
        mutationFn: (body: SelfProfileCreate) => unwrap(api.POST("/api/v1/members/me", { body })),
        onSuccess: () => {
            // The account is now linked: everything gated on membership must refetch.
            void qc.invalidateQueries({ queryKey: qk.me });
            void qc.invalidateQueries({ queryKey: qk.myMember });
            void qc.invalidateQueries({ queryKey: ["members"] });
        },
    });
}

/** Edit your own profile in place. Same fields as create; the scrape data is left alone. */
export function useUpdateMyProfile() {
    const qc = useQueryClient();
    return useMutation<MemberProfile, Error, SelfProfileCreate>({
        mutationFn: (body: SelfProfileCreate) => unwrap(api.PUT("/api/v1/members/me", { body })),
        onSuccess: (profile) => {
            // The card text everywhere reads from the member row we just changed.
            qc.setQueryData(qk.myMember, profile);
            void qc.invalidateQueries({ queryKey: qk.myMember });
            void qc.invalidateQueries({ queryKey: ["members"] });
        },
    });
}

/**
 * Who am I, and am I bound to a member row yet.
 *
 * `initialData` is what the server already had in hand for this render. Without
 * it a page renders its own header empty and asks for this again, behind the
 * session restore `useAuthedQueryOptions` waits on.
 */
export function useMe(initialData?: Me) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.me,
        queryFn: () => unwrap(api.GET("/api/v1/auth/me", {})),
        ...gate,
        initialData,
    });
}

export function useMyMember(initialData?: MemberProfile) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.myMember,
        queryFn: () => unwrap(api.GET("/api/v1/members/me", {})),
        ...gate,
        initialData,
    });
}

export function useMyEntry() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.myEntry,
        queryFn: () => unwrap(api.GET("/api/v1/members/me/entry", {})),
        ...gate,
    });
}

export function useSaveMyEntry() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: EntryUpsert) =>
            unwrap(api.PUT("/api/v1/members/me/entry", { body })),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: qk.myEntry });
            void qc.invalidateQueries({ queryKey: qk.myMember });
        },
    });
}

export function useMyIntents() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.myIntents,
        queryFn: () => unwrap(api.GET("/api/v1/members/me/intents", {})),
        ...gate,
    });
}

export function useSaveMyIntents() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: IntentsUpsert) =>
            unwrap(api.PUT("/api/v1/members/me/intents", { body })),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: qk.myIntents });
            void qc.invalidateQueries({ queryKey: ["members"] });
        },
    });
}

/**
 * The page size for the two lists `/me` displays, and the cap `PageParams`
 * allows.
 *
 * Both of them want the whole thing rather than a window on it, so both ask for
 * one page at the cap and read `total` for the honest count; `SavedList` says
 * "the most recent of N" on screen when there is more. Nothing decides anything
 * from these any more. Membership of the shortlist comes from `useSavedIds`,
 * and "have I already asked this person for an intro" is asked of the server
 * about that one member, so a long history cannot push the answer off the end
 * of a page.
 */
const DISPLAY_PAGE = 100;

export function useMySaved() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.mySaved,
        queryFn: () =>
            unwrap(api.GET("/api/v1/network/saved", { params: { query: { limit: DISPLAY_PAGE } } })),
        ...gate,
    });
}

/** Module scope: a stable reference is what lets React Query memoize the result. */
const toIdSet = (ids: SavedMemberIds) => new Set(ids.member_ids);

/**
 * The shortlist as a set of member ids.
 *
 * Its own endpoint and its own key, because a Save button asks something the
 * display page cannot answer. The page is cut at `DISPLAY_PAGE`, so reading
 * membership off it drew everybody below that row as unsaved, and clicking one
 * of those buttons sent a save that overwrote the note on a row that was
 * already there. `/network/saved/ids` is one uuid column bounded by the size of
 * one member's shortlist, so the whole set fits and the answer is an O(1)
 * lookup on it.
 */
export function useSavedIds() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.mySavedIds,
        queryFn: () => unwrap(api.GET("/api/v1/network/saved/ids", {})),
        select: toIdSet,
        ...gate,
    });
}

export type ToggleSavedVariables = {
    memberId: string;
    /** The state to move to, not the state it is in. */
    saved: boolean;
    /**
     * Left out, whatever note is on the row is kept: a Save button in a results
     * list knows nothing about a note written on the profile and must not speak
     * for it. `null` clears the note, a string sets it.
     */
    note?: string | null;
    /**
     * The row to show while the write is in flight. Every caller has the
     * Member in hand already, and without it the shortlist could only be
     * corrected after the round trip, which is the flicker this avoids.
     */
    member?: NetworkMember;
};

export function useToggleSaved() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ memberId, saved, note }: ToggleSavedVariables) => {
            const params = { path: { member_id: memberId } };
            if (!saved) {
                await unwrap(api.DELETE("/api/v1/network/saved/{member_id}", { params }));
                return null;
            }
            // An absent `note` is not the same as no note. The backend leaves
            // the stored one alone unless the key is present, so a save that
            // was told nothing about notes sends nothing about notes.
            return unwrap(
                api.PUT("/api/v1/network/saved/{member_id}", {
                    params,
                    body: note === undefined ? {} : { note },
                }),
            );
        },
        onMutate: async ({ memberId, saved, note, member }) => {
            // Prefix, so both the page and the id set stop refetching under the
            // optimistic write.
            await qc.cancelQueries({ queryKey: qk.mySaved });

            // The id set is what every button on screen is drawn from, so it
            // moves first and it moves whether or not the page is cached.
            const previousIds = qc.getQueryData<SavedMemberIds>(qk.mySavedIds);
            if (previousIds) {
                const has = previousIds.member_ids.includes(memberId);
                qc.setQueryData<SavedMemberIds>(qk.mySavedIds, {
                    member_ids: saved
                        ? has
                            ? previousIds.member_ids
                            : [memberId, ...previousIds.member_ids]
                        : previousIds.member_ids.filter((id) => id !== memberId),
                });
            }

            // The page is only cached once `/me` has been opened, so a save
            // from anywhere else has nothing to edit here and waits for
            // `onSettled`.
            const previous = qc.getQueryData<SavedMembersPage>(qk.mySaved);
            const context = { previous, previousIds };
            if (!previous) return context;

            if (!saved) {
                qc.setQueryData<SavedMembersPage>(qk.mySaved, {
                    items: previous.items.filter((row) => row.saved.saved_member_id !== memberId),
                    total: Math.max(0, previous.total - 1),
                });
                return context;
            }

            // Only the caller knows the Member; without one there is nothing
            // honest to draw, so the list waits for the server and the button
            // shows its own in-flight state from `variables` instead.
            const owner = qc.getQueryData<Me>(qk.me)?.member_id;
            if (!member || !owner) return context;
            if (previous.items.some((row) => row.saved.saved_member_id === memberId)) {
                return context;
            }

            qc.setQueryData<SavedMembersPage>(qk.mySaved, {
                items: [
                    {
                        member,
                        saved: {
                            owner_member_id: owner,
                            saved_member_id: memberId,
                            note: note ?? null,
                            created_at: new Date().toISOString(),
                        },
                    },
                    ...previous.items,
                ],
                total: previous.total + 1,
            });
            return context;
        },
        onError: (_error, _variables, context) => {
            if (context?.previous) qc.setQueryData(qk.mySaved, context.previous);
            if (context?.previousIds) qc.setQueryData(qk.mySavedIds, context.previousIds);
        },
        /**
         * The PUT answers with the row the server actually wrote, so the guessed
         * timestamp and note are replaced with the real ones in place.
         *
         * Only for a row the page already holds. Prepending an unknown row would
         * have to guess `total` too, and it cannot: the page is one window on
         * the shortlist, so a row missing from it does not mean the member was
         * not already saved. `onSettled` refetches and the server says.
         */
        onSuccess: (row, { memberId }) => {
            if (!row) return;
            qc.setQueryData<SavedMembersPage>(qk.mySaved, (page) => {
                if (!page?.items.some((item) => item.saved.saved_member_id === memberId)) {
                    return page;
                }
                return {
                    ...page,
                    items: page.items.map((item) =>
                        item.saved.saved_member_id === memberId ? row : item,
                    ),
                };
            });
        },
        /**
         * Prefix, so the page and the id set are both refetched. The optimistic
         * writes above are what makes the click feel instant; this is what makes
         * the result true, on the paths they cannot cover: an uncached page, an
         * unsave (which answers with nothing), and a `total` no client can work
         * out from one window on the list.
         */
        onSettled: () => qc.invalidateQueries({ queryKey: qk.mySaved }),
    });
}

/**
 * Intro requests, both directions.
 *
 * `withMemberId` narrows the page to the rows shared with one member, which is
 * the only honest way to answer "have I already asked this person". Filtering
 * the unfiltered list in the browser answered from one page at the cap, so a
 * member with a long history was told they had never asked and offered the form
 * a second time. Left out, this is the whole inbox, which is what `/me` shows.
 */
export function useMyIntros(withMemberId?: string) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.myIntrosList(withMemberId),
        queryFn: () =>
            unwrap(
                api.GET("/api/v1/network/intros", {
                    params: {
                        query: { with_member_id: withMemberId, limit: DISPLAY_PAGE },
                    },
                }),
            ),
        ...gate,
    });
}

export function useRequestIntro() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: { target_member_id: string; message: string }) =>
            unwrap(api.POST("/api/v1/network/intros", { body })),
        onSuccess: () => qc.invalidateQueries({ queryKey: qk.myIntros }),
    });
}

/**
 * Accepting or declining is a status change on one row, so the row changes
 * immediately and the request confirms it. The other rows are untouched, which
 * is what lets each of them keep its own buttons live.
 */
export function useRespondToIntro() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, status }: { id: string; status: IntroStatus }) =>
            unwrap(
                api.POST("/api/v1/network/intros/{request_id}/respond", {
                    params: { path: { request_id: id } },
                    body: { status },
                }),
            ),
        onMutate: async ({ id, status }) => {
            await qc.cancelQueries({ queryKey: qk.myIntros });
            // The inbox and the narrowed list on the other party's profile can
            // both be holding this row, so every list under the prefix moves.
            const previous = qc.getQueriesData<IntroRequestsPage>({ queryKey: qk.myIntros });
            qc.setQueriesData<IntroRequestsPage>({ queryKey: qk.myIntros }, (page) => {
                if (!page) return page;
                return {
                    ...page,
                    items: page.items.map((row) =>
                        row.request.id === id
                            ? { ...row, request: { ...row.request, status } }
                            : row,
                    ),
                };
            });
            return { previous };
        },
        onError: (_error, _variables, context) => {
            for (const [key, page] of context?.previous ?? []) qc.setQueryData(key, page);
        },
        // The response carries more than the status (the responder, the time it
        // was answered), and within `staleTime` nothing else would go and get
        // it, so the row would sit on the guess until the page was reloaded.
        onSettled: () => qc.invalidateQueries({ queryKey: qk.myIntros }),
    });
}
