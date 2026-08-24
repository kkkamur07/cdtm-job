"use client";

import { useAnnouncements, useMarkAnnouncementRead } from "@/api/hooks/community";
import type { Announcement } from "@/api/types";
import { ErrorState } from "@/components/states";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import RelativeTime from "@/components/RelativeTime";

/**
 * Announcements, newest first, unread ones marked. Reading is explicit: a card
 * marks itself read when it is expanded, not when it scrolls past, so the
 * unread count stays a count of things you have actually looked at.
 */
export default function AnnouncementList({
    limit,
    initial,
}: {
    limit?: number;
    initial?: { items: Announcement[]; total: number; unread: number };
}) {
    const announcements = useAnnouncements(initial);
    const markRead = useMarkAnnouncementRead();

    if (announcements.isPending) return <LoadingBlock label="Loading announcements" rows={2} />;
    if (announcements.error) {
        return <ErrorState error={announcements.error} onRetry={() => announcements.refetch()} />;
    }

    const items = announcements.data?.items ?? [];
    if (!items.length) {
        return <EmptyState title="No announcements yet" hint="CDTM posts here when there is news." />;
    }

    const shown = limit ? items.slice(0, limit) : items;

    return (
        <ul className="grid gap-2.5">
            {shown.map((item) => (
                <AnnouncementCard
                    key={item.id}
                    item={item}
                    onOpen={() => {
                        if (!item.is_read) markRead.mutate(item.id);
                    }}
                />
            ))}
        </ul>
    );
}

/** The opening of the body, on one line, for the collapsed card. */
function preview(body: string): string {
    return body.replace(/\s+/g, " ").trim().slice(0, 180);
}

function AnnouncementCard({ item, onOpen }: { item: Announcement; onOpen: () => void }) {
    const unread = !item.is_read;

    return (
        <li
            className={`grid grid-cols-[6px_1fr] overflow-hidden rounded-2xl border bg-white ${
                unread ? "border-[color:var(--blue-25)]" : "border-line"
            }`}
        >
            <span className={item.is_pinned ? "bg-green" : "bg-transparent"} aria-hidden="true" />
            <details className="group px-4 py-3.5" onToggle={(event) => event.currentTarget.open && onOpen()}>
                <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                    <span className="flex items-center gap-2 text-[12px] text-muted">
                        <span className="grid h-6 w-6 place-items-center rounded-full bg-blue text-[9px] font-bold text-white">
                            CDTM
                        </span>
                        <b className="font-semibold text-ink">CDTM</b>
                        <RelativeTime value={item.published_at ?? item.created_at} />
                        {item.is_pinned && <span className="pill pill-green">Pinned</span>}
                        {unread && (
                            <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-semibold text-blue">
                                <span className="h-2 w-2 rounded-full bg-blue" aria-hidden="true" />
                                New
                            </span>
                        )}
                    </span>
                    <span className="mt-1.5 block text-[15px] leading-snug font-semibold">
                        {item.title}
                    </span>
                    {/* The first line of the body, so the card says something
                        before it is opened. The full text is below. */}
                    <span className="mt-1 line-clamp-2 block text-[13px] text-muted group-open:hidden">
                        {preview(item.body)}
                    </span>
                    <span className="mt-1.5 block text-[12px] font-medium text-blue group-open:hidden">
                        Read announcement
                    </span>
                </summary>
                <p className="mt-2 text-[13.5px] leading-relaxed whitespace-pre-line">{item.body}</p>
                {typeof item.read_count === "number" && item.read_count > 0 && (
                    <p className="mt-2.5 text-[12px] text-muted">
                        {item.read_count === 1
                            ? "1 member has read this."
                            : `${item.read_count} members have read this.`}
                    </p>
                )}
            </details>
        </li>
    );
}
