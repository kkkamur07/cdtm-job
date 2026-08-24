"use client";

import Link from "next/link";

import { useEvents } from "@/api/hooks/community";
import type { CommunityEvent } from "@/api/types";
import { ErrorState } from "@/components/states";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import { EventRow } from "@/features/community/events/EventList";
import { useUrlState } from "@/lib/urlState";

type EventsPage = { items: CommunityEvent[]; total: number };

/**
 * The events list.
 *
 * The page fetches on the server and hands the result down as `initial`, so
 * this draws in the first paint. It stays a query underneath because an RSVP
 * has to move the counts in place, and the "Upcoming / All" choice lives in the
 * URL, so a filtered list is a link somebody can send.
 */
export default function EventsBody({
    upcoming,
    initial,
}: {
    upcoming: boolean;
    initial?: EventsPage;
}) {
    const events = useEvents(upcoming, initial);
    const { setParams } = useUrlState();

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <p className="eyebrow">Community</p>
                    <h1 className="text-xl font-semibold">Events</h1>
                    <p className="text-[13px] text-muted">
                        CDTM events, member meetups and things worth travelling for.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex h-10 items-center gap-0.5 rounded-[var(--radius-pill)] border border-line bg-white p-1">
                        {[
                            { value: true, label: "Upcoming" },
                            { value: false, label: "All" },
                        ].map((option) => (
                            <button
                                key={option.label}
                                type="button"
                                aria-pressed={upcoming === option.value}
                                onClick={() => setParams({ filter: option.value ? null : "all" })}
                                className={`h-8 rounded-[var(--radius-pill)] px-3 text-[13px] font-medium transition-colors ${
                                    upcoming === option.value
                                        ? "bg-blue text-white"
                                        : "text-muted hover:text-ink"
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                    <Link href="/announcements" className="btn">
                        Announcements
                    </Link>
                    <Link href="/events/new" className="btn btn-primary">
                        Add an event
                    </Link>
                </div>
            </header>

            <div className="card overflow-hidden">
                {events.isPending && <LoadingBlock label="Loading events" rows={4} />}
                {events.error && <ErrorState error={events.error} onRetry={() => events.refetch()} />}
                {events.data?.items.length === 0 && (
                    <EmptyState
                        title={upcoming ? "Nothing scheduled yet" : "No events on record"}
                        hint="Add one and everyone signed in will see it here."
                        action={
                            <Link href="/events/new" className="btn btn-sm">
                                Add an event
                            </Link>
                        }
                    />
                )}
                {events.data && events.data.items.length > 0 && (
                    <ul>
                        {events.data.items.map((event) => (
                            <EventRow key={event.id} event={event} />
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
