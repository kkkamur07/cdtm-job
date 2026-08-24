"use client";

import Link from "next/link";

import { useEvent } from "@/api/hooks/community";
import type { CommunityEvent } from "@/api/types";
import { ErrorState } from "@/components/states";
import { LoadingBlock } from "@/components/placeholders";
import { RsvpControl } from "@/features/community/events/EventList";
import { formatDateTime, humanise, safeUrl } from "@/lib/format";

/**
 * One event. The page fetches it on the server and passes it in, so this paints
 * immediately; it stays a query because RSVPing has to update the counts on
 * this screen without a round trip through the server render.
 */
export default function EventBody({ id, initial }: { id: string; initial?: CommunityEvent }) {
    const event = useEvent(id, initial);

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <Link href="/events" className="w-fit text-[12.5px] font-medium text-blue hover:underline">
                Back to events
            </Link>

            <article className="card p-6">
                {event.isPending && <LoadingBlock label="Loading event" rows={3} />}
                {event.error && <ErrorState error={event.error} onRetry={() => event.refetch()} />}
                {event.data && (
                    <>
                        <p className="eyebrow capitalize">{humanise(event.data.kind)}</p>
                        <h1 className="mt-1 text-2xl leading-tight font-semibold">{event.data.title}</h1>
                        <p className="mt-2 text-[13.5px] text-muted">
                            {[formatDateTime(event.data.starts_at), event.data.location]
                                .filter(Boolean)
                                .join(" · ")}
                        </p>
                        {event.data.ends_at && (
                            <p className="text-[13px] text-muted">
                                Until {formatDateTime(event.data.ends_at)}
                            </p>
                        )}

                        <div className="mt-4 flex flex-wrap items-center gap-3">
                            <RsvpControl event={event.data} />
                            <span className="text-[12.5px] text-muted">
                                {event.data.going_count ?? 0} going · {event.data.interested_count ?? 0}{" "}
                                interested
                            </span>
                        </div>

                        {event.data.description && (
                            <div className="prose mt-5 border-t border-line pt-5">
                                <p className="whitespace-pre-line">{event.data.description}</p>
                            </div>
                        )}

                        {safeUrl(event.data.url) && (
                            <a
                                href={safeUrl(event.data.url)!}
                                target="_blank"
                                rel="noreferrer noopener"
                                className="btn btn-blue mt-5"
                            >
                                Open event page
                            </a>
                        )}
                    </>
                )}
            </article>
        </div>
    );
}
