"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useMySaved, useToggleSaved } from "@/api/hooks/me";
import { avatarOf } from "@/api/people";
import type { NetworkMember } from "@/api/types";
import { AvatarCircle } from "@/components/MemberAvatar";
import { ErrorState } from "@/components/states";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import { memberSubtitle } from "@/features/community/members/MemberRow";

/** What a removal has to remember to be able to put itself back. */
type Removed = { member: NetworkMember; note: string | null };

const UNDO_MS = 10_000;

/** Your shortlist, with the note you left on each person. */
export default function SavedList() {
    const saved = useMySaved();
    const toggle = useToggleSaved();
    const [confirming, setConfirming] = useState<string | null>(null);
    const [removed, setRemoved] = useState<Removed | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // The undo offer expires, and it must not outlive the component.
    useEffect(() => {
        if (!removed) return;
        timer.current = setTimeout(() => setRemoved(null), UNDO_MS);
        return () => {
            if (timer.current) clearTimeout(timer.current);
        };
    }, [removed]);

    if (saved.isPending) return <LoadingBlock label="Loading saved people" rows={3} />;
    if (saved.error) return <ErrorState error={saved.error} onRetry={() => saved.refetch()} />;
    if (!saved.data?.length && !removed) {
        return (
            <EmptyState
                title="Nothing saved yet"
                hint="Save people from the network and they collect here with your notes."
                action={
                    <Link href="/network" className="btn btn-sm">
                        Open the network
                    </Link>
                }
            />
        );
    }

    const remove = (member: NetworkMember, note: string | null) => {
        setConfirming(null);
        setRemoved({ member, note });
        toggle.mutate({ memberId: member.id, saved: false, member });
    };

    const undo = () => {
        if (!removed) return;
        toggle.mutate({
            memberId: removed.member.id,
            saved: true,
            note: removed.note,
            member: removed.member,
        });
        setRemoved(null);
    };

    return (
        <>
            {removed && (
                <p
                    role="status"
                    className="flex flex-wrap items-center gap-2 border-b border-line bg-cream px-3.5 py-2.5 text-[13px]"
                >
                    Removed <b className="font-semibold">{removed.member.name}</b> from your saved
                    people.
                    <button type="button" className="btn btn-sm" onClick={undo}>
                        Undo
                    </button>
                </p>
            )}

            <ul>
                {(saved.data ?? []).map(({ member, saved: record }) => {
                    const busy = toggle.isPending && toggle.variables?.memberId === member.id;
                    return (
                        <li
                            key={member.id}
                            className="flex items-start gap-3 border-t border-line px-3.5 py-3 first:border-t-0"
                        >
                            <AvatarCircle name={member.name} avatar={avatarOf(member)} px={44} />
                            <div className="min-w-0 flex-1">
                                <Link
                                    href={`/members/${member.slug}`}
                                    className="text-[13.5px] font-semibold hover:text-blue"
                                >
                                    {member.name}
                                </Link>
                                <p className="truncate text-xs text-muted">{memberSubtitle(member)}</p>
                                {record.note ? (
                                    <p className="mt-1.5 inline-block max-w-full rounded-[10px] bg-green-soft px-2.5 py-1.5 text-[12.5px]">
                                        {record.note}
                                    </p>
                                ) : (
                                    <p className="mt-1.5 text-[12px] text-muted">No note.</p>
                                )}
                            </div>

                            {/* Removing a person also throws away the note that
                                went with them, so it asks first rather than
                                acting on one stray click. */}
                            {confirming === member.id ? (
                                <span className="flex shrink-0 items-center gap-1.5">
                                    <span className="text-[12px] text-muted">Remove?</span>
                                    <button
                                        type="button"
                                        className="btn btn-sm"
                                        disabled={busy}
                                        onClick={() => remove(member, record.note ?? null)}
                                    >
                                        Yes
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-ghost"
                                        onClick={() => setConfirming(null)}
                                    >
                                        Keep
                                    </button>
                                </span>
                            ) : (
                                <button
                                    type="button"
                                    className="btn btn-sm btn-ghost shrink-0"
                                    disabled={busy}
                                    onClick={() => setConfirming(member.id)}
                                >
                                    Remove
                                    <span className="sr-only"> {member.name} from saved people</span>
                                </button>
                            )}
                        </li>
                    );
                })}
            </ul>
        </>
    );
}
