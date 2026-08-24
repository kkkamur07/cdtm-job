"use client";

import Link from "next/link";
import { useId, useRef } from "react";

import { useMe, useMyMember } from "@/api/hooks/me";
import type { Me, MemberProfile } from "@/api/types";
import Panel from "@/components/Panel";
import { useSession } from "@/auth/AuthProvider";
import { useUrlState } from "@/lib/urlState";
import EditProfileForm from "@/features/community/me/EditProfileForm";
import EntryForm from "@/features/community/me/EntryForm";
import IntentsForm from "@/features/community/me/IntentsForm";
import IntrosList from "@/features/community/me/IntrosList";
import SavedList from "@/features/community/me/SavedList";

type Tab = "profile" | "entry" | "intents" | "saved" | "intros";

const TABS: { key: Tab; label: string }[] = [
    { key: "profile", label: "Profile" },
    { key: "entry", label: "Your entry" },
    { key: "intents", label: "Open to" },
    { key: "saved", label: "Saved people" },
    { key: "intros", label: "Intro requests" },
];

function isTab(value: string | null): value is Tab {
    return TABS.some((item) => item.key === value);
}

/**
 * Your own account, in four tabs.
 *
 * They are real tabs, not buttons wearing tab roles: arrow keys and Home/End
 * move between them, only the selected one is in the tab order, and each names
 * the panel it controls. Announcing "tab" and then behaving like a row of
 * buttons is worse than no role at all, because it promises a keyboard model
 * that is not there.
 *
 * Which tab is open lives in the URL, so "here is my saved list" is a link
 * somebody can actually follow.
 */
export default function MeBody({
    me: initialMe,
    member: initialMember,
}: {
    /** What the server already fetched, so the header paints from the HTML. */
    me?: Me;
    member?: MemberProfile;
}) {
    const { params, setParams } = useUrlState();
    const fromUrl = params.get("tab");
    const tab: Tab = isTab(fromUrl) ? fromUrl : "entry";
    const setTab = (next: Tab) => setParams({ tab: next === "entry" ? null : next });

    const tabsRef = useRef<(HTMLButtonElement | null)[]>([]);
    const baseId = useId();
    const me = useMe(initialMe);
    const member = useMyMember(initialMember);
    const { signOut } = useSession();

    /** Move selection and focus together, wrapping at both ends. */
    const select = (index: number) => {
        const wrapped = (index + TABS.length) % TABS.length;
        setTab(TABS[wrapped].key);
        tabsRef.current[wrapped]?.focus();
    };

    const onKeyDown = (event: React.KeyboardEvent, index: number) => {
        const moves: Record<string, number> = {
            ArrowRight: index + 1,
            ArrowLeft: index - 1,
            Home: 0,
            End: TABS.length - 1,
        };
        const next = moves[event.key];
        if (next === undefined) return;
        event.preventDefault();
        select(next);
    };

    return (
        <div className="shell grid gap-4 py-4 pb-12">
            <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <p className="eyebrow">You</p>
                    {/* Community says Member, so the page is headed with the
                        Member's name; the account name is the fallback for
                        somebody not matched to a roster entry yet. */}
                    <h1 className="text-xl font-semibold">
                        {member.data?.name ?? me.data?.account.full_name ?? "Your account"}
                    </h1>
                    <p className="text-[13px] text-muted">
                        {me.data?.account.email}
                        {member.data?.slug && (
                            <>
                                {" · "}
                                <Link href={`/members/${member.data.slug}`} className="text-blue hover:underline">
                                    View your public entry
                                </Link>
                            </>
                        )}
                    </p>
                </div>
                <button type="button" className="btn btn-sm" onClick={() => void signOut()}>
                    Sign out
                </button>
            </header>

            <div
                role="tablist"
                aria-label="Your account"
                className="flex flex-wrap gap-0.5 rounded-[var(--radius-pill)] bg-white p-1"
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
                            className={`h-8 rounded-[var(--radius-pill)] px-3.5 text-[13px] font-medium transition-colors ${
                                active ? "bg-blue text-white" : "text-muted hover:text-ink"
                            }`}
                        >
                            {item.label}
                        </button>
                    );
                })}
            </div>

            {TABS.map((item) => (
                <div
                    key={item.key}
                    role="tabpanel"
                    id={`${baseId}-panel-${item.key}`}
                    aria-labelledby={`${baseId}-tab-${item.key}`}
                    hidden={tab !== item.key}
                    tabIndex={0}
                >
                    {/* Each panel mounts only while it is the open one: these
                        are four separate forms and lists, and there is nothing
                        to gain from keeping the other three alive. */}
                    {tab === item.key && item.key === "profile" && (
                        <Panel title="Your profile">
                            <EditProfileForm />
                        </Panel>
                    )}
                    {tab === item.key && item.key === "entry" && (
                        <Panel title="Your entry">
                            <EntryForm />
                        </Panel>
                    )}
                    {tab === item.key && item.key === "intents" && (
                        <Panel title="What you are open to">
                            <IntentsForm />
                        </Panel>
                    )}
                    {tab === item.key && item.key === "saved" && (
                        <section className="card overflow-hidden">
                            <SavedList />
                        </section>
                    )}
                    {tab === item.key && item.key === "intros" && (
                        <section className="card overflow-hidden">
                            <IntrosList />
                        </section>
                    )}
                </div>
            ))}
        </div>
    );
}
