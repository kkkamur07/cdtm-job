import { loadEvents } from "@/api/server";
import MemberGate, { gatedData } from "@/components/MemberGate";
import EventsBody from "./Client";

export const metadata = { title: "Events · CDTM Community" };

type Params = { searchParams: Promise<{ filter?: string }> };

/**
 * "Upcoming" is the default and carries no parameter; `?filter=all` is the
 * other reading of the same list. Keeping it in the URL means the server can
 * fetch the right list before the page is sent, rather than the browser
 * fetching it again after hydration.
 */
export default async function EventsPage({ searchParams }: Params) {
    const { filter } = await searchParams;
    const upcoming = filter !== "all";

    // Started before the gate suspends on /auth/me, so the list is in flight
    // while the gate decides rather than a round trip behind it.
    const events = gatedData(() => loadEvents(upcoming).catch(() => undefined));

    return (
        <MemberGate next="/events">
            <Events upcoming={upcoming} events={events} />
        </MemberGate>
    );
}

async function Events({
    upcoming,
    events,
}: {
    upcoming: boolean;
    events: Promise<Awaited<ReturnType<typeof loadEvents>> | undefined | null>;
}) {
    return <EventsBody upcoming={upcoming} initial={(await events) ?? undefined} />;
}
