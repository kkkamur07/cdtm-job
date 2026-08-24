"use client";

import Link from "next/link";

import { useRsvp } from "@/api/hooks/community";
import type { CommunityEvent, RsvpStatus } from "@/api/types";
import { dateParts, formatDateTime } from "@/lib/format";

const RSVPS: { value: RsvpStatus; label: string }[] = [
    { value: "going", label: "Going" },
    { value: "interested", label: "Interested" },
];

/** A row per event: date block, what and where, and your RSVP. */
export function EventRow({ event, compact = false }: { event: CommunityEvent; compact?: boolean }) {
    const date = dateParts(event.starts_at);

    return (
        <li className="flex items-center gap-3.5 border-t border-line px-4 py-3.5 first:border-t-0">
            {date && (
                <span className="w-14 shrink-0 border-r border-line pr-3 text-center" aria-hidden="true">
                    <b className="block text-xl leading-none font-semibold">{date.day}</b>
                    <span className="text-[11px] tracking-[0.08em] text-muted uppercase">{date.month}</span>
                </span>
            )}
            <span className="min-w-0 flex-1">
                <Link href={`/events/${event.id}`} className="text-sm font-semibold hover:text-blue">
                    {event.title}
                </Link>
                <span className="mt-0.5 block truncate text-[12.5px] text-muted">
                    {[formatDateTime(event.starts_at), event.location].filter(Boolean).join(" · ")}
                </span>
                {!compact && (
                    <span className="mt-1.5 flex flex-wrap gap-1.5">
                        <span className="pill pill-muted">{event.kind}</span>
                        <span className="pill pill-muted">{event.going_count ?? 0} going</span>
                        <span className="pill pill-muted">{event.interested_count ?? 0} interested</span>
                    </span>
                )}
            </span>
            {!compact && <RsvpControl event={event} />}
        </li>
    );
}

export function RsvpControl({ event }: { event: CommunityEvent }) {
    const rsvp = useRsvp();
    // Keyed by the event being answered, so one RSVP in flight never disables
    // the controls on the rest of the list.
    const busy = rsvp.isPending && rsvp.variables?.id === event.id;

    return (
        <span className="flex shrink-0 gap-1.5">
            {RSVPS.map((option) => {
                const active = event.my_rsvp === option.value;
                return (
                    <button
                        key={option.value}
                        type="button"
                        className="chip"
                        aria-pressed={active}
                        disabled={busy}
                        onClick={() =>
                            rsvp.mutate({ id: event.id, status: active ? null : option.value })
                        }
                    >
                        {option.label}
                    </button>
                );
            })}
        </span>
    );
}
