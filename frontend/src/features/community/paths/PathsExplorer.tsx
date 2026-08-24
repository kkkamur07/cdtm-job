"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";

import { usePathFlow, usePathMembers } from "@/api/hooks/community";
import type { DirectoryFacets, PathFlow, PathGroups } from "@/api/types";
import { avatarOf } from "@/api/people";
import { AvatarCircle } from "@/components/MemberAvatar";
import { ErrorState } from "@/components/states";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import AskLine from "../ask/AskLine";
import AskAnalysis from "../ask/AskAnalysis";
import { useAsk } from "../ask/useAsk";
import { STAGE_LABELS } from "./layout";

// The chart is a few kilobytes of SVG maths that nothing above the fold needs,
// so it is split out and loaded once this page is on screen.
const PathsChart = dynamic(() => import("./PathsChart"), {
    ssr: false,
    loading: () => <LoadingBlock label="Drawing the flow" rows={4} />,
});

type Band = { stage: string; group: string };

const ASK_EXAMPLES = [
    "physicists who founded something in their first step",
    "Fall 2019, did consulting, now operators in Berlin",
    "who moved abroad after CDTM",
];

/**
 * The aggregate view: what people studied, the first thing they did after CDTM,
 * and where they are now.
 *
 * Two ways in, and they answer the same question at different resolutions. The
 * class filter and a click on a group narrow the whole community down; a
 * plain-words question narrows it to the people one sentence describes, and
 * redraws the same diagram over just them.
 */
export default function PathsExplorer({
    initialFlow,
    groups,
    facets,
}: {
    initialFlow: PathFlow;
    groups: PathGroups;
    facets: DirectoryFacets | null;
}) {
    const [classId, setClassId] = useState<number | undefined>(undefined);
    const [band, setBand] = useState<Band | null>(null);
    const [question, setQuestion] = useState("");

    const flow = usePathFlow(classId ? { class_id: classId } : {});
    const members = usePathMembers(band ? { ...band, class_id: classId } : null);
    const answer = useAsk(question, { enabled: question.length > 0 });

    // A question replaces the diagram with the paths of whoever it found. When
    // there is no question, the class filter decides what is drawn.
    const asked = Boolean(question) && Boolean(answer.data?.flow);
    const shown = asked ? answer.data!.flow! : (flow.data ?? initialFlow);
    const classes = facets?.classes ?? [];

    return (
        <>
            <AskLine
                placeholder="who studied physics and then went into VC…"
                examples={ASK_EXAMPLES}
                value={question}
                busy={answer.isFetching}
                onAsk={(text) => {
                    setQuestion(text);
                    setBand(null);
                }}
                onClear={() => setQuestion("")}
            >
                {question && (
                    <AskAnalysis
                        question={question}
                        interpretation={answer.data?.interpretation}
                        total={answer.data?.total}
                        loading={answer.isFetching}
                        error={answer.error}
                    />
                )}
            </AskLine>

            <div className="mb-4 flex flex-wrap items-center gap-2">
                <label className="label mb-0" htmlFor="paths-class">
                    Class
                </label>
                <select
                    id="paths-class"
                    className="select w-auto"
                    value={classId ?? ""}
                    disabled={asked}
                    onChange={(event) => {
                        setClassId(event.target.value ? Number(event.target.value) : undefined);
                        setBand(null);
                    }}
                >
                    <option value="">All classes</option>
                    {classes.map((entry) => (
                        <option key={entry.id} value={entry.id}>
                            {entry.label}
                        </option>
                    ))}
                </select>
                {asked && (
                    <span className="text-[12px] text-muted">
                        Showing the people your question found. Clear it to filter by class again.
                    </span>
                )}
            </div>

            <div className="card paths-wrap p-4 sm:px-5">
                <div className="paths">
                    <PathsChart
                        flow={shown}
                        selected={band}
                        onSelect={asked ? undefined : setBand}
                        perPerson={asked}
                    />
                </div>
                <div className="legend">
                    <span>
                        <i style={{ background: "#fff", border: "1px solid var(--color-line)" }} />
                        Group
                    </span>
                    <span>
                        <i style={{ background: "var(--color-blue)", opacity: 0.2 }} />
                        {asked
                            ? "One line per member"
                            : "Members moving between groups, width is the count"}
                    </span>
                    {!asked && (
                        <span>
                            <i style={{ background: "var(--color-green)", opacity: 0.8 }} />
                            Selected group
                        </span>
                    )}
                    <span className="ml-auto tabular-nums">
                        {shown.members_counted} members counted
                    </span>
                </div>
            </div>

            {!asked && (
                <section className="mt-6">
                    <h2 className="label">
                        {band
                            ? `On this band: ${STAGE_LABELS[band.stage] ?? band.stage} · ${band.group}`
                            : "Pick a group"}
                    </h2>

                    {!band && (
                        <p className="text-[13.5px] text-muted">
                            Select a group in the diagram to see who is in it.{" "}
                            {groups.study.length > 0 && (
                                <>Fields of study include {groups.study.slice(0, 3).join(", ")}.</>
                            )}
                        </p>
                    )}

                    {band && members.isPending && <LoadingBlock label="Loading members" />}
                    {band && members.error && (
                        <ErrorState error={members.error} onRetry={() => members.refetch()} />
                    )}
                    {band && members.data?.items.length === 0 && (
                        <EmptyState title="Nobody in this group yet." />
                    )}

                    {band && members.data && members.data.items.length > 0 && (
                        <ul className="card mt-2 overflow-hidden [content-visibility:auto]">
                            {members.data.items.map((member) => (
                                <li key={member.id} className="cv-row">
                                    <Link href={`/members/${member.slug}`} className="rrow">
                                        <AvatarCircle
                                            name={member.name}
                                            avatar={avatarOf(member)}
                                            px={48}
                                        />
                                        <span className="min-w-0">
                                            <span className="block truncate text-sm font-semibold">
                                                {member.name}
                                            </span>
                                            <span className="s block truncate">
                                                {[member.title, member.company, member.class_label]
                                                    .filter(Boolean)
                                                    .join(" · ")}
                                            </span>
                                        </span>
                                        <span className="text-[12px] text-muted">Open</span>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </section>
            )}

            {asked && (answer.data?.members?.length ?? 0) > 0 && (
                <section className="mt-6">
                    <h2 className="label">Who your question found</h2>
                    <ul className="card mt-2 overflow-hidden [content-visibility:auto]">
                        {answer.data!.members!.map((member) => (
                            <li key={member.id} className="cv-row">
                                <Link href={`/members/${member.slug}`} className="rrow">
                                    <AvatarCircle
                                        name={member.name}
                                        avatar={member.avatar}
                                        px={48}
                                    />
                                    <span className="min-w-0">
                                        <span className="block truncate text-sm font-semibold">
                                            {member.name}
                                        </span>
                                        <span className="s block truncate">
                                            {[member.title, member.company, member.class_label]
                                                .filter(Boolean)
                                                .join(" · ")}
                                        </span>
                                    </span>
                                    <span className="text-[12px] text-muted">Open</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                    <p className="mt-3 text-[12.5px]">
                        <Link
                            href={`/network?q=${encodeURIComponent(question)}`}
                            className="font-medium text-blue hover:underline"
                        >
                            Open this question in Ask the network
                        </Link>
                    </p>
                </section>
            )}
        </>
    );
}
