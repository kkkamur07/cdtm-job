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
 * `/network/saved` is a paged list like every other one, and 100 is the cap
 * `PageParams` allows. Both readers want the whole shortlist rather than a window
 * on it, so both ask for the first page at the cap; `total` is the honest count.
 * A member with more than a hundred saved people would see the hundred most recent,
 * which is the point at which this needs a real pager.
 */
const SHORTLIST_LIMIT = 100;

const savedPage = () =>
    unwrap(api.GET("/api/v1/network/saved", { params: { query: { limit: SHORTLIST_LIMIT } } }));

export function useMySaved() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.mySaved,
        queryFn: savedPage,
        ...gate,
    });
}

/** Module scope, so the projection below is memoized on the cached page. */
const savedIds = (page: SavedMembersPage) =>
    new Set(page.items.map((row) => row.saved.saved_member_id));

/**
 * The same shortlist, as a set of member ids.
 *
 * Every row on a results page holds a save button, and each one used to scan
 * the whole shortlist to find out whether it was in it. `select` runs once per
 * cache entry rather than once per row per render, and the answer is an O(1)
 * lookup.
 */
export function useSavedIds() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.mySaved,
        queryFn: savedPage,
        select: savedIds,
        ...gate,
    });
}

export type ToggleSavedVariables = {
    memberId: string;
    /** The state to move to, not the state it is in. */
    saved: boolean;
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
            return unwrap(
                api.PUT("/api/v1/network/saved/{member_id}", {
                    params,
                    body: { note: note ?? null },
                }),
            );
        },
        onMutate: async ({ memberId, saved, note, member }) => {
            await qc.cancelQueries({ queryKey: qk.mySaved });
            const previous = qc.getQueryData<SavedMembersPage>(qk.mySaved);
            if (!previous) return { previous };

            if (!saved) {
                qc.setQueryData<SavedMembersPage>(qk.mySaved, {
                    items: previous.items.filter((row) => row.saved.saved_member_id !== memberId),
                    total: Math.max(0, previous.total - 1),
                });
                return { previous };
            }

            // Only the caller knows the Member; without one there is nothing
            // honest to draw, so the list waits for the server and the button
            // shows its own in-flight state from `variables` instead.
            const owner = qc.getQueryData<Me>(qk.me)?.member_id;
            if (!member || !owner) return { previous };
            if (previous.items.some((row) => row.saved.saved_member_id === memberId)) {
                return { previous };
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
            return { previous };
        },
        onError: (_error, _variables, context) => {
            if (context?.previous) qc.setQueryData(qk.mySaved, context.previous);
        },
        /**
         * The PUT answers with the row the server actually wrote, so the guessed
         * timestamp is replaced with the real one in place. Re-fetching the whole
         * shortlist to learn one `created_at` was a page of JSON for a field that
         * arrived in the response body of the write itself.
         */
        onSuccess: (row, { memberId }) => {
            if (!row) return;
            qc.setQueryData<SavedMembersPage>(qk.mySaved, (page) => {
                if (!page) return page;
                const known = page.items.some((item) => item.saved.saved_member_id === memberId);
                return {
                    items: known
                        ? page.items.map((item) =>
                              item.saved.saved_member_id === memberId ? row : item,
                          )
                        : [row, ...page.items],
                    total: known ? page.total : page.total + 1,
                };
            });
        },
    });
}

export function useMyIntros() {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.myIntros,
        queryFn: () =>
            unwrap(
                api.GET("/api/v1/network/intros", {
                    params: { query: { limit: SHORTLIST_LIMIT } },
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
            const previous = qc.getQueryData<IntroRequestsPage>(qk.myIntros);
            if (previous) {
                qc.setQueryData<IntroRequestsPage>(qk.myIntros, {
                    ...previous,
                    items: previous.items.map((row) =>
                        row.request.id === id
                            ? { ...row, request: { ...row.request, status } }
                            : row,
                    ),
                });
            }
            return { previous };
        },
        onError: (_error, _variables, context) => {
            if (context?.previous) qc.setQueryData(qk.myIntros, context.previous);
        },
    });
}
