"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import type { Member } from "@/api/types";
import { AvatarCircle } from "@/components/MemberAvatar";
import SearchIcon from "@/components/SearchIcon";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import IntentPills from "../IntentPills";
import SaveButton from "../SaveButton";
import IntroRequest from "../members/IntroRequest";
import AskAnalysis from "./AskAnalysis";
import Typewriter from "./Typewriter";
import { whyMatched } from "./filters";
import { isNotReady, useAsk } from "./useAsk";

// The flow diagram is SVG maths nothing above the fold needs, and an answer
// often has no flow at all, so it is split out of the first load.
const PathsChart = dynamic(() => import("@/features/community/paths/PathsChart"), {
    ssr: false,
    loading: () => <LoadingBlock label="Drawing the paths" rows={3} />,
});

const EXAMPLES = [
    "co-founders in Berlin working on climate or AI",
    "who can I ask about moving to SF on an O-1?",
    "PMs in Munich open to mentoring a first-time PM",
    "who went from consulting to founding a startup?",
];

/**
 * Ask the network.
 *
 * One question, one answer, three ways of reading it: the sentence the model
 * wrote back, the paths of the people it found, and the people themselves.
 * Picking a person from the chart and picking one from the list are the same
 * selection, so the two views never disagree about who is being looked at.
 *
 * The question lives in the URL. A question worth asking is worth sending to
 * somebody, and coming back to a link should not mean retyping it.
 */
export default function AskExplorer() {
    const router = useRouter();
    const params = useSearchParams();
    const question = params.get("q") ?? "";

    const [draft, setDraft] = useState(question);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const answer = useAsk(question);
    const members = useMemo(() => answer.data?.members ?? [], [answer.data]);
    const interpretation = answer.data?.interpretation;
    const flow = answer.data?.flow ?? null;

    const ask = useCallback(
        (text: string) => {
            const next = text.trim();
            setDraft(next);
            setSelectedId(null);
            router.replace(next ? `/network?q=${encodeURIComponent(next)}` : "/network", {
                scroll: false,
            });
        },
        [router],
    );

    const selected = members.find((member) => member.id === selectedId) ?? null;
    const asking = answer.isFetching;

    return (
        <div className="explore">
            <div className="explore-head">
                <p className="eyebrow">Ask the network</p>
                <h1>Ask in plain words.</h1>
                <p className="desc">
                    Intents, places, topics and career paths. We turn the question into filters over
                    members and their paths, then show who matches and how they got there.
                </p>
            </div>

            <Typewriter phrases={EXAMPLES} />

            <form
                className="card qbar"
                role="search"
                onSubmit={(event) => {
                    event.preventDefault();
                    if (asking) return;
                    ask(draft);
                }}
            >
                <SearchIcon />
                <label className="sr-only" htmlFor="ask-question">
                    Ask the network
                </label>
                <input
                    id="ask-question"
                    name="q"
                    value={draft}
                    maxLength={300}
                    autoComplete="off"
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="Ask anything about CDTM people…"
                />
                {/* Disabled while a question is in flight as well as when the
                    box is too short: a second Enter used to fire a second
                    request over the top of the first. */}
                <button
                    type="submit"
                    className="btn btn-blue"
                    disabled={asking || draft.trim().length < 3}
                >
                    {asking ? "Exploring…" : "Explore"}
                </button>
            </form>

            <div className="suggest">
                {EXAMPLES.map((example) => (
                    <button key={example} type="button" onClick={() => ask(example)}>
                        {example}
                    </button>
                ))}
            </div>

            {question && (
                <AskAnalysis
                    question={question}
                    interpretation={interpretation}
                    total={answer.data?.total}
                    loading={asking}
                    error={answer.error}
                />
            )}

            {flow && flow.nodes && flow.nodes.length > 0 && (
                <>
                    <div className="card chart">
                        <PathsChart flow={flow} perPerson />
                    </div>
                    <p className="statsbar">
                        <span>
                            <b className="tabular-nums">{flow.members_counted}</b>{" "}
                            {flow.members_counted === 1 ? "member" : "members"}
                        </span>
                        <span>
                            <b className="tabular-nums">{countStage(flow, "study")}</b> fields of
                            study
                        </span>
                        <span>
                            <b className="tabular-nums">{countStage(flow, "first_step")}</b> first
                            careers
                        </span>
                        <span>Pick a row below to follow one person</span>
                    </p>
                </>
            )}

            {selected && (
                <SelectedBar member={selected} onClose={() => setSelectedId(null)} />
            )}

            <div className="results">
                {question && asking && members.length === 0 && !answer.error && (
                    <LoadingBlock label="Asking the network" rows={4} />
                )}

                {question && !asking && !answer.error && members.length === 0 && (
                    <EmptyState
                        title="Nobody matched that."
                        hint="Try naming a place, a company, or one thing you would want to ask about."
                    />
                )}

                {question && answer.error && isNotReady(answer.error) && (
                    <EmptyState
                        title="Ask is not switched on here."
                        hint="Browse the directory in the meantime."
                        action={
                            <Link href="/paths" className="btn btn-sm mt-1">
                                Open Paths
                            </Link>
                        }
                    />
                )}

                {members.length > 0 && (
                    <>
                        <p className="mb-2.5 text-[13px] text-muted">
                            Sorted by match, then recently updated.
                        </p>
                        <ul className="card overflow-hidden [content-visibility:auto]">
                            {members.map((member) => (
                                <ResultRow
                                    key={member.id}
                                    member={member}
                                    filters={interpretation?.filters}
                                    selected={member.id === selectedId}
                                    onSelect={() =>
                                        setSelectedId(member.id === selectedId ? null : member.id)
                                    }
                                />
                            ))}
                        </ul>
                    </>
                )}
            </div>
        </div>
    );
}

function countStage(flow: { nodes?: { stage: string }[] | null }, stage: string): number {
    return (flow.nodes ?? []).filter((node) => node.stage === stage).length;
}

/**
 * One person in the answer.
 *
 * The row is a button, because clicking it selects rather than navigates; the
 * name inside is a link, so opening the entry in a new tab still works.
 */
function ResultRow({
    member,
    filters,
    selected,
    onSelect,
}: {
    member: Member;
    filters?: Record<string, unknown> | null;
    selected: boolean;
    onSelect: () => void;
}) {
    const reasons = whyMatched(member, filters);
    const subtitle = [member.title, member.company, member.location, member.class_label]
        .filter(Boolean)
        .join(" · ");

    return (
        <li className={`cv-row relative ${selected ? "bg-blue-soft" : ""}`}>
            <button
                type="button"
                className="rrow rrow-actions w-full text-left"
                aria-pressed={selected}
                onClick={onSelect}
            >
                <AvatarCircle name={member.name} avatar={member.avatar} px={48} />
                <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">
                        {member.name}
                    </span>
                    <span className="s block truncate">{subtitle}</span>
                    {reasons.length > 0 && (
                        <span className="why block truncate">
                            {reasons.map((reason, index) => (
                                <span key={`${reason.prefix}-${reason.highlight}`}>
                                    {index > 0 && " · "}
                                    {reason.prefix} <mark>{reason.highlight}</mark>
                                </span>
                            ))}
                        </span>
                    )}
                </span>
                <span className="hidden sm:block">
                    <IntentPills intents={member.intents} max={2} />
                </span>
            </button>
            <span className="rowacts">
                <Link
                    href={`/members/${member.slug}`}
                    className="text-[12px] font-medium text-blue hover:underline"
                >
                    Open entry
                </Link>
                <SaveButton memberId={member.id} label={false} />
            </span>
        </li>
    );
}

/** The bar that appears once somebody is picked, with the actions for them. */
function SelectedBar({ member, onClose }: { member: Member; onClose: () => void }) {
    return (
        <div className="card selbar" role="status">
            <AvatarCircle name={member.name} avatar={member.avatar} px={32} />
            <span className="nm">{member.name}</span>
            <span className="hl truncate">
                {[member.headline, member.location].filter(Boolean).join(" · ")}
            </span>
            <SaveButton memberId={member.id} />
            <span className="intro">
                <IntroRequest memberId={member.id} name={member.name} />
            </span>
            <Link href={`/members/${member.slug}`} className="btn btn-sm">
                Open entry
            </Link>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
                Close
                <span className="sr-only"> the selected member</span>
            </button>
        </div>
    );
}
