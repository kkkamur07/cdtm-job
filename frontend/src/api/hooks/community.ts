"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "../client";
import { qk } from "../keys";
import type {
    Announcement,
    AnnouncementCreate,
    CommunityEvent,
    CommunityEventSummary,
    EventCreate,
    HousingCreate,
    HousingUpdate,
    PathFlow,
    RsvpStatus,
} from "../types";
import { useAuthedQueryOptions } from "./shared";

type AnnouncementsPage = { items: Announcement[]; total: number; unread: number };
/**
 * The list route ships rows without the description; the by-id and RSVP routes ship
 * the whole event. A whole event fits a row slot, which is what lets the confirmed
 * RSVP below be written straight into the cached list.
 */
type EventsPage = { items: CommunityEventSummary[]; total: number };

/* ---------------------------------------------------------------- events */

/**
 * Both event reads take what the server already fetched.
 *
 * The page is rendered on the server, so the list is on screen in the first
 * paint and these never wait on a round trip. They stay queries rather than
 * plain props because an RSVP has to move the counts under the reader's hand,
 * and that is an edit to a cache, not to a serialized prop.
 */
export function useEvents(upcoming = true, initialData?: EventsPage) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.events(upcoming),
        queryFn: () =>
            unwrap(api.GET("/api/v1/events/", { params: { query: { upcoming, limit: 100 } } })),
        ...gate,
        initialData,
    });
}

export function useEvent(id: string | null, initialData?: CommunityEvent) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.event(id ?? ""),
        queryFn: () =>
            unwrap(api.GET("/api/v1/events/{event_id}", { params: { path: { event_id: id! } } })),
        ...gate,
        enabled: gate.enabled && Boolean(id),
        initialData,
    });
}

export function useCreateEvent() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: EventCreate) => unwrap(api.POST("/api/v1/events/", { body })),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
    });
}

/**
 * An RSVP is one boolean-ish field and two counters, all of which the browser
 * already knows how to recompute, so the row flips the moment it is clicked and
 * the request only confirms it. `onError` puts the snapshot back, which is what
 * makes that honest rather than a lie that happens to be true most of the time.
 */
function withRsvp<T extends Pick<CommunityEventSummary, "my_rsvp" | "going_count" | "interested_count">>(
    event: T,
    next: RsvpStatus | null,
): T {
    const before = event.my_rsvp ?? null;
    if (before === next) return event;
    const delta = (status: RsvpStatus) =>
        (next === status ? 1 : 0) - (before === status ? 1 : 0);
    return {
        ...event,
        my_rsvp: next,
        going_count: Math.max(0, (event.going_count ?? 0) + delta("going")),
        interested_count: Math.max(0, (event.interested_count ?? 0) + delta("interested")),
    };
}

export function useRsvp() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, status }: { id: string; status: RsvpStatus | null }) =>
            unwrap(
                api.PUT("/api/v1/events/{event_id}/rsvp", {
                    params: { path: { event_id: id } },
                    body: { status },
                }),
            ),
        onMutate: async ({ id, status }) => {
            await qc.cancelQueries({ queryKey: ["events"] });
            await qc.cancelQueries({ queryKey: qk.event(id) });

            const lists = qc.getQueriesData<EventsPage>({ queryKey: ["events"] });
            const one = qc.getQueryData<CommunityEvent>(qk.event(id));

            for (const [key, page] of lists) {
                if (!page) continue;
                qc.setQueryData<EventsPage>(key, {
                    ...page,
                    items: page.items.map((item) =>
                        item.id === id ? withRsvp(item, status) : item,
                    ),
                });
            }
            if (one) qc.setQueryData<CommunityEvent>(qk.event(id), withRsvp(one, status));

            return { lists, one };
        },
        onError: (_error, { id }, context) => {
            for (const [key, page] of context?.lists ?? []) qc.setQueryData(key, page);
            if (context?.one) qc.setQueryData(qk.event(id), context.one);
        },
        // The server is the authority on the counts once it has answered, so
        // the confirmed row replaces the guess rather than a whole refetch.
        onSuccess: (updated, { id }) => {
            if (!updated) return;
            qc.setQueryData<CommunityEvent>(qk.event(id), updated);
            for (const [key, page] of qc.getQueriesData<EventsPage>({ queryKey: ["events"] })) {
                if (!page) continue;
                qc.setQueryData<EventsPage>(key, {
                    ...page,
                    items: page.items.map((item) => (item.id === id ? updated : item)),
                });
            }
        },
    });
}

/* --------------------------------------------------------- announcements */

/**
 * `initialData` is what the server already fetched for this render. Passing it
 * in means the list paints from the server payload and only refetches when it
 * goes stale, instead of flashing a skeleton on every navigation.
 */
export function useAnnouncements(initialData?: AnnouncementsPage, limit = 50) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.announcementList(limit),
        queryFn: () =>
            unwrap(api.GET("/api/v1/announcements/", { params: { query: { limit } } })),
        ...gate,
        initialData,
    });
}

export function useCreateAnnouncement() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: AnnouncementCreate) =>
            unwrap(api.POST("/api/v1/announcements/", { body })),
        onSuccess: () => qc.invalidateQueries({ queryKey: qk.announcements }),
    });
}

/**
 * Opening an announcement flips one boolean and one counter.
 *
 * It used to refetch all fifty announcements to learn that, which is a page of
 * JSON to discover something the browser already knew. Every cached list is
 * edited instead (the home widget and the board hold separate pages), and
 * put back if the write fails.
 */
export function useMarkAnnouncementRead() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (id: string) =>
            unwrap(
                api.POST("/api/v1/announcements/{announcement_id}/read", {
                    params: { path: { announcement_id: id } },
                }),
            ),
        onMutate: async (id) => {
            await qc.cancelQueries({ queryKey: qk.announcements });
            const previous = qc.getQueriesData<AnnouncementsPage>({ queryKey: qk.announcements });
            qc.setQueriesData<AnnouncementsPage>({ queryKey: qk.announcements }, (page) => {
                if (!page) return page;
                const target = page.items.find((item) => item.id === id);
                if (!target || target.is_read) return page;
                return {
                    ...page,
                    unread: Math.max(0, page.unread - 1),
                    items: page.items.map((item) =>
                        item.id === id
                            ? {
                                  ...item,
                                  is_read: true,
                                  read_count:
                                      typeof item.read_count === "number"
                                          ? item.read_count + 1
                                          : item.read_count,
                              }
                            : item,
                    ),
                };
            });
            return { previous };
        },
        onError: (_error, _id, context) => {
            for (const [key, page] of context?.previous ?? []) qc.setQueryData(key, page);
        },
    });
}

/* --------------------------------------------------------------- housing */

export function useHousingListing(id: string | null) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.housingListing(id ?? ""),
        queryFn: () =>
            unwrap(
                api.GET("/api/v1/housing/{listing_id}", {
                    params: { path: { listing_id: id! } },
                }),
            ),
        ...gate,
        enabled: gate.enabled && Boolean(id),
    });
}

/**
 * A write to one listing refetches the boards and that listing. Every other
 * cached listing stays put; before this every housing query was thrown away.
 */
function invalidateListing(qc: ReturnType<typeof useQueryClient>, id: string) {
    return Promise.all([
        qc.invalidateQueries({ queryKey: ["housing", "list"] }),
        qc.invalidateQueries({ queryKey: qk.housingListing(id) }),
    ]);
}

export function useCreateHousing() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: HousingCreate) => unwrap(api.POST("/api/v1/housing/", { body })),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["housing", "list"] }),
    });
}

export function useUpdateHousing(id: string) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: HousingUpdate) =>
            unwrap(
                api.PATCH("/api/v1/housing/{listing_id}", {
                    params: { path: { listing_id: id } },
                    body,
                }),
            ),
        onSuccess: () => invalidateListing(qc, id),
    });
}

/**
 * Renew: push the expiry sixty days out and reopen the listing.
 *
 * The board hides expired listings, so an owner whose room is still free needs
 * one button rather than a re-post. Owner or admin only, which the API enforces.
 */
export function useRenewHousing(id: string) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: () =>
            unwrap(
                api.POST("/api/v1/housing/{listing_id}/renew", {
                    params: { path: { listing_id: id } },
                }),
            ),
        onSuccess: () => invalidateListing(qc, id),
    });
}

/* ----------------------------------------------------------------- paths */

type FlowParams = { class_id?: number; study_group?: string };

/**
 * `initialData` is the flow the server already drew for this render.
 *
 * The flow is computed over every member's career history, so it is the most
 * expensive read on the site. Without this the browser asked for the identical
 * unfiltered flow again the moment it hydrated, and the page cost twice what it
 * had to. Only the caller knows whether its params match what the server
 * fetched, so it decides whether to pass it.
 */
export function usePathFlow(params: FlowParams, initialData?: PathFlow) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.pathsFlow(params),
        queryFn: () => unwrap(api.GET("/api/v1/paths/flow", { params: { query: params } })),
        ...gate,
        initialData,
        placeholderData: (previous) => previous,
    });
}

export function usePathMembers(args: { stage: string; group: string; class_id?: number } | null) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.pathsMembers(args),
        queryFn: () =>
            unwrap(
                api.GET("/api/v1/paths/members", {
                    params: { query: { ...args!, limit: 60 } },
                }),
            ),
        ...gate,
        enabled: gate.enabled && Boolean(args),
    });
}
