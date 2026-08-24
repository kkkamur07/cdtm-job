import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/errors";
import { loadEvent } from "@/api/server";
import MemberGate from "@/components/MemberGate";
import { LoadingBlock } from "@/components/placeholders";
import { formatDateTime } from "@/lib/format";
import EventBody from "./Client";

type Params = { params: Promise<{ id: string }> };

/** `loadEvent` is `React.cache`d, so the title costs no extra request. */
export async function generateMetadata({ params }: Params) {
    const { id } = await params;
    try {
        const event = await loadEvent(id);
        return {
            title: `${event.title} · CDTM Community`,
            description:
                [formatDateTime(event.starts_at), event.location].filter(Boolean).join(" · ") ||
                undefined,
        };
    } catch {
        return { title: "Event · CDTM Community" };
    }
}

export default async function EventPage({ params }: Params) {
    const { id } = await params;
    return (
        <MemberGate next={`/events/${id}`}>
            <Suspense fallback={<EventSkeleton />}>
                <Event id={id} />
            </Suspense>
        </MemberGate>
    );
}

async function Event({ id }: { id: string }) {
    const event = await loadEvent(id).catch((error) => {
        if (error instanceof ApiError && error.isNotFound) return null;
        throw error;
    });

    if (!event) notFound();

    return <EventBody id={id} initial={event} />;
}

function EventSkeleton() {
    return (
        <div className="shell py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading event" rows={4} />
            </div>
        </div>
    );
}
