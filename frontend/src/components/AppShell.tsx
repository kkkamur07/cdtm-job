"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AvatarCircle } from "./MemberAvatar";

const NAV = [
    { href: "/", label: "Home" },
    { href: "/network", label: "Ask the network" },
    { href: "/directory", label: "Directory" },
    { href: "/announcements", label: "Announcements" },
    { href: "/events", label: "Events" },
    { href: "/housing", label: "Housing" },
    { href: "/jobs", label: "Jobs" },
    { href: "/paths", label: "Paths" },
];

/** /jobs stays lit while you read a job; /events while you read an event. */
function isCurrent(pathname: string, href: string): boolean {
    if (href === "/") return pathname === "/";
    if (href === "/network") return pathname === "/network" || pathname.startsWith("/members/");
    if (href === "/events") return pathname.startsWith("/events");
    if (href === "/jobs") return pathname.startsWith("/jobs") || pathname.startsWith("/companies");
    return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Masthead and navigation, on every screen inside the app.
 *
 * Seven destinations is few enough to lay out in one row and swipe through on
 * a phone, so there is no hamburger: a menu that has to be opened would hide
 * the unread count that is half the reason to come back.
 *
 * That count is announcements, so it sits on Announcements. It used to hang off
 * Events, which sent everybody who followed it to the wrong page.
 *
 * This is the app's only always-mounted client component, and it takes four
 * scalars rather than the whole account object, so the serialized payload on
 * every page stays a few dozen bytes.
 */
export default function AppShell({
    children,
    signedIn,
    name,
    avatarUrl,
    unread,
}: {
    children: React.ReactNode;
    signedIn: boolean;
    name: string | null;
    avatarUrl: string | null;
    unread: number;
}) {
    const pathname = usePathname();
    const firstName = name?.split(/\s+/)[0] ?? null;

    return (
        <div className="min-h-screen">
            <header className="sticky top-0 z-40 border-b border-line/70 bg-cream/90 backdrop-blur-md">
                <div className="shell-wide flex flex-wrap items-center gap-x-5 gap-y-2 py-3">
                    <Link
                        href="/"
                        className="group flex shrink-0 items-center"
                        aria-label="CDTM Community, home"
                    >
                        <img
                            src="/assets/cdtm.svg"
                            alt=""
                            width={32}
                            height={32}
                            className="h-8 w-auto transition-transform duration-500 ease-out group-hover:-translate-y-0.5 group-hover:rotate-6"
                        />
                        <span className="mr-2 ml-3 h-5 w-px bg-ink" />
                        <span className="text-[15px] font-semibold text-blue">Community</span>
                        <span className="ml-2 rounded-full border border-blue/30 bg-blue-soft px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue">
                            Beta
                        </span>
                    </Link>

                    <nav aria-label="Sections" className="order-3 min-w-0 flex-1 basis-full sm:order-none sm:basis-auto">
                        <ul className="-mx-1 flex gap-0.5 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                            {NAV.map((item) => {
                                const current = isCurrent(pathname, item.href);
                                return (
                                    <li key={item.href}>
                                        <Link
                                            href={item.href}
                                            aria-current={current ? "page" : undefined}
                                            className={`inline-flex items-center rounded-[var(--radius-pill)] px-3 py-1.5 text-[13.5px] font-medium whitespace-nowrap transition-colors ${
                                                current
                                                    ? "bg-blue-soft text-blue"
                                                    : "text-muted hover:bg-white hover:text-ink"
                                            }`}
                                        >
                                            {item.label}
                                            {item.href === "/announcements" && unread > 0 && (
                                                <span className="count-pill">{unread}</span>
                                            )}
                                        </Link>
                                    </li>
                                );
                            })}
                        </ul>
                    </nav>

                    <div className="ml-auto flex shrink-0 items-center gap-2.5">
                        {signedIn ? (
                            <>
                                <Link href="/post" className="btn btn-sm">
                                    + Post
                                </Link>
                                <Link
                                    href="/me"
                                    className="flex items-center gap-2 rounded-full py-0.5 pr-2.5 pl-0.5 transition-colors hover:bg-white"
                                >
                                    <AvatarCircle
                                        name={name ?? "You"}
                                        avatar={avatarUrl ? { sm: avatarUrl, lg: avatarUrl } : null}
                                        px={28}
                                    />
                                    <span className="hidden text-[13px] font-semibold sm:inline">
                                        {firstName ?? "You"}
                                    </span>
                                </Link>
                            </>
                        ) : (
                            <Link href="/login" className="btn btn-sm btn-blue">
                                Sign in
                            </Link>
                        )}
                    </div>
                </div>
            </header>

            <main id="main">{children}</main>
        </div>
    );
}
