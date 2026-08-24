import { loadEvents } from "@/api/server";
import MemberGate from "@/components/MemberGate";
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

    return (
        <MemberGate next="/events">
            <Events upcoming={upcoming} />
        </MemberGate>
    );
}

async function Events({ upcoming }: { upcoming: boolean }) {
    const events = await loadEvents(upcoming).catch(() => undefined);
    return <EventsBody upcoming={upcoming} initial={events} />;
}
