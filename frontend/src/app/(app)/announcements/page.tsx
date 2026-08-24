import { loadAnnouncements, loadMe } from "@/api/server";
import MemberGate from "@/components/MemberGate";
import AnnouncementList from "@/features/community/announcements/AnnouncementList";
import AnnouncementComposer from "./Client";

export const metadata = { title: "Announcements · CDTM Community" };

export default function AnnouncementsPage() {
    return (
        <MemberGate next="/announcements">
            <Announcements />
        </MemberGate>
    );
}

/**
 * The list and "am I an admin" are independent, so they go out together. Both
 * are read here rather than in the browser: the page used to render a skeleton,
 * hydrate, and only then ask for the announcements it exists to show.
 */
async function Announcements() {
    const [announcements, me] = await Promise.all([
        loadAnnouncements().catch(() => undefined),
        loadMe().catch(() => null),
    ]);

    return (
        <div className="shell grid gap-4 py-4 pb-12">
            <header>
                <p className="eyebrow">From CDTM</p>
                <h1 className="text-xl font-semibold">Announcements</h1>
                <p className="text-[13px] text-muted">
                    Open one to read it. Opening it marks it read and clears it from your unread count.
                </p>
            </header>

            {me?.is_admin && <AnnouncementComposer />}

            <AnnouncementList initial={announcements} />
        </div>
    );
}
