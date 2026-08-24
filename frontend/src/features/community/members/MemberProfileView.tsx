"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";

import type { MemberPath, MemberProfile } from "@/api/types";
import MemberAvatar from "@/components/MemberAvatar";
import { safeUrl } from "@/lib/format";
import IntentPills from "../IntentPills";
import IntroRequest from "./IntroRequest";
import MemberPositions from "./MemberPositions";
import PathStrip from "../paths/PathStrip";
import SaveButton from "../SaveButton";
import { memberSubtitle } from "./MemberRow";

type Tab = "entry" | "path" | "positions";

const TABS: { key: Tab; label: string }[] = [
    { key: "entry", label: "Entry" },
    { key: "path", label: "Path" },
    { key: "positions", label: "Positions" },
];

/**
 * One member, shown the same way in the side panel on /network and on their
 * own page. The three tabs are the three questions people actually arrive
 * with: who are you, how did you get there, and what have you done.
 *
 * They are real tabs, not buttons wearing tab roles: arrow keys and Home/End
 * move between them, only the selected one is in the tab order, and each is
 * wired to the panel it controls. Announcing "tab" and then behaving like a
 * toolbar is worse than no role at all, because it promises a keyboard model
 * that is not there.
 *
 * The name is the page's `h1` where this is the page, and an `h2` where it
 * sits inside a panel under one. The sections inside follow it down a level,
 * so neither use skips a rank.
 */
export default function MemberProfileView({
    profile,
    path,
    nameAs = "h2",
    showPageLink = false,
    onClose,
}: {
    profile: MemberProfile;
    /** Read from `/paths/members/{slug}`, which the page fetches in parallel. */
    path?: MemberPath | null;
    /** `h1` when this view is the page; `h2` when it sits inside one. */
    nameAs?: "h1" | "h2";
    /** The panel links out to the full page; the page itself does not. */
    showPageLink?: boolean;
    onClose?: () => void;
}) {
    const [tab, setTab] = useState<Tab>("entry");
    const tabsRef = useRef<(HTMLButtonElement | null)[]>([]);
    const baseId = useId();
    const linkedin = safeUrl(profile.linkedin_url);
    const subtitle = memberSubtitle(profile);

    const Name = nameAs;
    const sectionLevel = nameAs === "h1" ? "h2" : "h3";

    const select = (index: number) => {
        const next = TABS[(index + TABS.length) % TABS.length];
        setTab(next.key);
        tabsRef.current[(index + TABS.length) % TABS.length]?.focus();
    };

    const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
        if (event.key === "ArrowRight") {
            event.preventDefault();
            select(index + 1);
        } else if (event.key === "ArrowLeft") {
            event.preventDefault();
            select(index - 1);
        } else if (event.key === "Home") {
            event.preventDefault();
            select(0);
        } else if (event.key === "End") {
            event.preventDefault();
            select(TABS.length - 1);
        }
    };

    return (
        <div>
            <div className="flex items-start gap-4 border-b border-line p-5">
                <span className="block h-16 w-16 shrink-0 overflow-hidden rounded-full bg-cream">
                    <MemberAvatar name={profile.name} avatar={profile.avatar} size="lg" priority />
                </span>
                <div className="min-w-0 flex-1">
                    <Name className="text-xl leading-tight font-semibold">{profile.name}</Name>
                    {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        {profile.class_label && <span className="pill pill-class">{profile.class_label}</span>}
                        {profile.is_ca && <span className="pill pill-ca">CA</span>}
                        {profile.major && <span className="pill pill-muted">{profile.major}</span>}
                        {profile.location && <span className="pill pill-muted">{profile.location}</span>}
                    </div>
                </div>
                {onClose && (
                    <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>
                        Close
                    </button>
                )}
            </div>

            <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
                <SaveButton memberId={profile.id} member={profile} />
                <IntroRequest memberId={profile.id} name={profile.name} />
                {linkedin && (
                    <a href={linkedin} target="_blank" rel="noreferrer noopener" className="btn btn-sm">
                        LinkedIn
                    </a>
                )}
                {showPageLink && (
                    <Link href={`/members/${profile.slug}`} className="btn btn-sm btn-ghost">
                        Open page
                    </Link>
                )}
            </div>

            <div className="px-5 pt-4">
                <div
                    role="tablist"
                    aria-label="Member sections"
                    className="inline-flex gap-0.5 rounded-[var(--radius-pill)] bg-cream p-[3px]"
                >
                    {TABS.map((item, index) => {
                        const active = tab === item.key;
                        return (
                            <button
                                key={item.key}
                                ref={(node) => {
                                    tabsRef.current[index] = node;
                                }}
                                type="button"
                                role="tab"
                                id={`${baseId}-tab-${item.key}`}
                                aria-controls={`${baseId}-panel-${item.key}`}
                                aria-selected={active}
                                // Roving tab index: one stop for the whole set,
                                // then the arrow keys move within it.
                                tabIndex={active ? 0 : -1}
                                onClick={() => setTab(item.key)}
                                onKeyDown={(event) => onKeyDown(event, index)}
                                className={`h-7 rounded-[var(--radius-pill)] px-3 text-[12.5px] font-medium transition-colors ${
                                    active
                                        ? "bg-white text-blue shadow-[0_1px_2px_rgb(0_0_0/0.06)]"
                                        : "text-muted hover:text-ink"
                                }`}
                            >
                                {item.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {TABS.map((item) => (
                <div
                    key={item.key}
                    role="tabpanel"
                    id={`${baseId}-panel-${item.key}`}
                    aria-labelledby={`${baseId}-tab-${item.key}`}
                    hidden={tab !== item.key}
                    tabIndex={0}
                    className="grid gap-5 p-5"
                >
                    {item.key === "entry" && <EntryTab profile={profile} level={sectionLevel} />}
                    {item.key === "path" && <PathStrip path={path} />}
                    {item.key === "positions" && (
                        <MemberPositions
                            positions={profile.positions ?? []}
                            educations={profile.educations ?? []}
                            level={sectionLevel}
                        />
                    )}
                </div>
            ))}
        </div>
    );
}

type Level = "h2" | "h3";

function EntryTab({ profile, level }: { profile: MemberProfile; level: Level }) {
    const entry = profile.entry;
    const about = entry?.about ?? profile.summary;

    return (
        <>
            {entry?.ask_me_about && (
                <div className="rounded-2xl bg-green-soft px-3.5 py-3 text-[13.5px]">
                    <b className="font-semibold">Ask me about</b> {entry.ask_me_about}
                </div>
            )}

            <Section title="Open to" level={level}>
                {profile.intents ? (
                    <IntentPills intents={profile.intents} max={6} />
                ) : (
                    <p className="text-[13px] text-muted">Nothing set yet.</p>
                )}
                {profile.intents?.note && (
                    <p className="mt-2 text-[13px] text-muted">{profile.intents.note}</p>
                )}
            </Section>

            {about && (
                <Section title="About" level={level}>
                    <p className="text-[13.5px] leading-relaxed whitespace-pre-line">{about}</p>
                </Section>
            )}

            {entry?.topics && entry.topics.length > 0 && (
                <Section title="Topics" level={level}>
                    <PillList items={entry.topics} />
                </Section>
            )}

            {entry?.hobbies && entry.hobbies.length > 0 && (
                <Section title="Outside work" level={level}>
                    <PillList items={entry.hobbies} />
                </Section>
            )}

            {profile.skills && profile.skills.length > 0 && (
                <Section title="Skills" level={level}>
                    <PillList items={profile.skills.slice(0, 16)} />
                </Section>
            )}

            {!profile.is_claimed && (
                <p className="text-[12.5px] text-muted">
                    This entry comes from the roster and LinkedIn. Nobody has signed in and claimed it yet.
                </p>
            )}
        </>
    );
}

function Section({
    title,
    level,
    children,
}: {
    title: string;
    level: Level;
    children: React.ReactNode;
}) {
    const Heading = level;
    return (
        <section>
            <Heading className="mb-2.5 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">
                {title}
            </Heading>
            {children}
        </section>
    );
}

function PillList({ items }: { items: string[] }) {
    return (
        <div className="flex flex-wrap gap-1.5">
            {items.map((item) => (
                <span key={item} className="pill pill-outline">
                    {item}
                </span>
            ))}
        </div>
    );
}
