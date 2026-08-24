import Link from "next/link";

import { loadMe } from "@/api/server";
import MemberGate from "@/components/MemberGate";

export const metadata = { title: "Post · CDTM Community" };

const OPTIONS = [
    {
        href: "/jobs/new",
        title: "A job",
        description: "A role at your company or team. Shows up in Jobs and on your entry.",
    },
    {
        href: "/housing/new",
        title: "A housing listing",
        description: "A room, a sublet, a couch, or what you are looking for.",
    },
    {
        href: "/events/new",
        title: "An event",
        description: "Meetups, roundtables, a dinner in your city. Anyone can host.",
    },
];

/** One chooser behind the header's "+ Post", rather than four separate entry points. */
export default function PostPage() {
    return (
        <MemberGate requireMember next="/post">
            <Chooser />
        </MemberGate>
    );
}

async function Chooser() {
    const me = await loadMe().catch(() => null);

    return (
        <div className="shell pb-16">
            <div className="pt-3 pb-5">
                <p className="eyebrow">Post</p>
                <h1 className="mt-1 text-[26px] font-semibold">What do you want to share?</h1>
                <p className="mt-2 max-w-[56ch] text-[14px] text-muted">
                    Everything is visible to signed-in members only and shows your name, so people
                    can ask you directly.
                </p>
            </div>

            <div className="choose">
                {OPTIONS.map((option) => (
                    <Link key={option.href} href={option.href} className="card">
                        <h3>{option.title}</h3>
                        <p>{option.description}</p>
                    </Link>
                ))}

                {me?.is_admin ? (
                    <Link href="/announcements" className="card">
                        <h3>
                            An announcement
                            <span className="pill pill-muted ml-1.5 align-middle">Admins</span>
                        </h3>
                        <p>Pinned posts from CDTM, with a read count.</p>
                    </Link>
                ) : (
                    <div className="card opacity-60" aria-disabled="true">
                        <h3>
                            An announcement
                            <span className="pill pill-muted ml-1.5 align-middle">Admins</span>
                        </h3>
                        <p>Only community admins can post announcements.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
