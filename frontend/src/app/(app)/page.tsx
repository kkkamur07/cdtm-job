import Link from "next/link";

import {
    loadAnnouncements,
    loadCompany,
    loadEvents,
    loadHousing,
    loadJobs,
    loadMe,
    loadMembers,
    loadMemberIndex,
    loadMyMember,
    loadMyIntents,
    loadMySaved,
} from "@/api/server";
import MemberGate, { gatedData } from "@/components/MemberGate";
import Panel from "@/components/Panel";
import { avatarOf } from "@/api/people";
import { AvatarCircle } from "@/components/MemberAvatar";
import AnnouncementList from "@/features/community/announcements/AnnouncementList";
import { EventRow } from "@/features/community/events/EventList";
import IntentPills from "@/features/community/IntentPills";
import AskBar from "@/features/community/home/AskBar";
import PeopleStrip from "@/features/community/home/PeopleStrip";
import JobRow from "@/features/jobboard/JobRow";
import { toJobRow } from "@/features/jobboard/jobData";
import { firstName, weekdayName } from "@/lib/format";
import { INTENTS, activeIntents } from "@/lib/intents";

/**
 * Synchronous on purpose: the feed is started here, before the gate suspends on
 * `/auth/me`, so the eight reads begin at the same moment the gate's own does
 * rather than a full round trip after it.
 */
export default function HomePage() {
    const data = gatedData(loadFeed);
    return (
        <MemberGate next="/">
            <Feed data={data} />
        </MemberGate>
    );
}

/**
 * The home feed.
 *
 * Eight independent reads, one round of `Promise.all`. Awaiting them in
 * sequence would stack eight latencies on top of each other for a page whose
 * whole job is to load fast enough to be worth opening.
 */
async function loadFeed() {
    const [me, member, intents, saved, announcements, events, jobs, housing] =
        await Promise.all([
            loadMe(),
            loadMyMember().catch(() => null),
            loadMyIntents().catch(() => null),
            loadMySaved().catch(() => ({ items: [], total: 0 })),
            loadAnnouncements(2).catch(() => null),
            loadEvents(true).catch(() => null),
            loadJobs({ status: "published", limit: 3 }),
            loadHousing({ status: "open", limit: 1 }).catch(() => null),
        ]);

    const myIntents = activeIntents(intents);
    const focus = myIntents[0] ?? "cofounding";

    // These depend on the first wave: the peers on which intent came back, the
    // posters and the companies on the ids the jobs carry. They still go out
    // together. The feed shows three jobs, so it reads at most three companies
    // by id; it used to pull a hundred of them to name three.
    const companyIds = [
        ...new Set(jobs.items.map((job) => job.company_id).filter((id): id is string => Boolean(id))),
    ];
    const [peers, members, companyList] = await Promise.all([
        loadMembers({ intent: focus, limit: 5 }).catch(() => null),
        loadMemberIndex(jobs.items.map((job) => job.posted_by_member_id)).catch(() => null),
        Promise.all(companyIds.map((id) => loadCompany(id).catch(() => null))),
    ]);

    return {
        me,
        member,
        intents,
        myIntents,
        focus,
        saved,
        announcements,
        events,
        jobs,
        housing,
        peers,
        members,
        companyList,
    };
}

async function Feed({ data }: { data: Promise<Awaited<ReturnType<typeof loadFeed>> | null> }) {
    const loaded = await data;
    // Only reachable signed in: the gate has shown the notice otherwise.
    if (!loaded) return null;

    const {
        me,
        member,
        intents,
        myIntents,
        focus,
        saved,
        announcements,
        events,
        jobs,
        housing,
        peers,
        members,
        companyList,
    } = loaded;

    const focusLabel = INTENTS.find((item) => item.key === focus)?.label ?? "co-founding";
    const peerList = (peers?.items ?? []).filter((member) => member.id !== me.member_id).slice(0, 4);

    const byCompany = new Map(
        companyList.filter((company) => company !== null).map((company) => [company.id, company]),
    );
    const jobRows = jobs.items.map((job) =>
        toJobRow(
            job,
            job.company_id ? byCompany.get(job.company_id) : undefined,
            job.posted_by_member_id ? members?.get(job.posted_by_member_id) : null,
        ),
    );

    // Community says Member, so the greeting uses the Member's own name when
    // the account is claimed. The account name is the fallback for someone who
    // has signed in but is not matched to a roster entry yet.
    const name = member?.name ?? me.account.full_name ?? me.account.email ?? "there";
    const avatar = member?.avatar ?? (me.account.avatar_url
        ? { sm: me.account.avatar_url, lg: me.account.avatar_url }
        : null);
    const unread = announcements?.unread ?? 0;
    const today = weekdayName();

    return (
        <div className="shell-wide">
            <div className="home">
                <div className="grid gap-6">
                    <div className="hero">
                        <p className="hero-eyebrow">
                            {today}
                            {unread > 0 ? `, ${unread} new since your last visit` : ""}
                        </p>
                        <h1 className="text-[28px] font-semibold">Hello, {firstName(name)}.</h1>
                        <p className="max-w-[52ch] text-[14.5px] text-white/75">
                            Ask the network, or see who is around. Everything here is posted by
                            members, and everything shows who to ask.
                        </p>
                        <AskBar />
                    </div>

                    <Panel
                        title="Announcements"
                        badge={unread}
                        action={{ href: "/announcements", label: "All" }}
                    >
                        <AnnouncementList limit={2} initial={announcements ?? undefined} />
                    </Panel>

                    {peerList.length > 0 && (
                        <Panel
                            title={`Open to ${focusLabel.toLowerCase()}, like you`}
                            action={{ href: "/network", label: "See all" }}
                        >
                            <PeopleStrip members={peerList} />
                        </Panel>
                    )}

                    <Panel
                        title="Jobs from members"
                        action={{ href: "/jobs", label: `All ${jobs.total} jobs` }}
                    >
                        <ul className="jlist -mx-4 -mb-4">
                            {jobRows.slice(0, 2).map((job) => (
                                <JobRow key={job.id} job={job} compact />
                            ))}
                        </ul>
                    </Panel>
                </div>

                <div className="grid gap-6">
                    <Panel title="Your entry" action={{ href: "/me", label: "Edit" }}>
                        <div className="flex items-center gap-3">
                            <AvatarCircle name={name} avatar={avatar} px={48} />
                            <div className="min-w-0">
                                <div className="truncate text-[15px] font-semibold">{name}</div>
                                <div className="truncate text-[13px] text-muted">
                                    {[member?.title, member?.company].filter(Boolean).join(", ") ||
                                        me.account.email}
                                </div>
                            </div>
                        </div>
                        {myIntents.length > 0 ? (
                            <IntentPills intents={intents} className="mt-3" max={5} />
                        ) : (
                            <p className="mt-3 text-[13px] text-muted">
                                You have not said what you are open to yet.{" "}
                                <Link href="/me" className="font-medium text-blue hover:underline">
                                    Add it
                                </Link>
                                .
                            </p>
                        )}
                    </Panel>

                    <Panel
                        title="Saved people"
                        action={{ href: "/me", label: `All ${saved.total}` }}
                    >
                        {saved.items.length ? (
                            <>
                                <div className="saved-rail">
                                    {saved.items.slice(0, 4).map((entry) => (
                                        <Link
                                            key={entry.member.id}
                                            href={`/members/${entry.member.slug}`}
                                            className="mini"
                                        >
                                            <span className="mx-auto mb-1.5 block w-fit">
                                                <AvatarCircle
                                                    name={entry.member.name}
                                                    avatar={avatarOf(entry.member)}
                                                    px={56}
                                                />
                                            </span>
                                            <span className="n block truncate">
                                                {firstName(entry.member.name)}
                                            </span>
                                            <span className="s block truncate">
                                                {entry.member.company ?? ""}
                                            </span>
                                        </Link>
                                    ))}
                                </div>
                                {saved.items[0]?.saved.note && (
                                    <p className="note mt-3">
                                        {saved.items[0].saved.note}{" "}
                                        <span className="text-muted">
                                            · {firstName(saved.items[0].member.name)}
                                        </span>
                                    </p>
                                )}
                            </>
                        ) : (
                            <p className="text-[13px] text-muted">
                                Save people as you meet them and they show up here.
                            </p>
                        )}
                    </Panel>

                    <Panel title="Coming up" action={{ href: "/events", label: "All events" }}>
                        {events?.items.length ? (
                            <ul className="-mx-4 -mb-4">
                                {events.items.slice(0, 2).map((event) => (
                                    <EventRow key={event.id} event={event} compact />
                                ))}
                            </ul>
                        ) : (
                            <p className="text-[13px] text-muted">Nothing on the calendar yet.</p>
                        )}
                    </Panel>

                    <div className="quiet-links">
                        <Link href="/housing" className="card quiet">
                            <span className="k">Housing</span>
                            <span className="v">
                                {housing?.total ?? 0} open listing
                                {housing?.total === 1 ? "" : "s"}
                            </span>
                        </Link>
                        <Link href="/paths" className="card quiet">
                            <span className="k">Paths</span>
                            <span className="v">Where your class went</span>
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
