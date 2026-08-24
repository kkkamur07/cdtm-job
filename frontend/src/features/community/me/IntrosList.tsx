"use client";

import Link from "next/link";

import { useMe, useMyIntros, useRespondToIntro } from "@/api/hooks/me";
import { avatarOf } from "@/api/people";
import { AvatarCircle } from "@/components/MemberAvatar";
import { ErrorState } from "@/components/states";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import RelativeTime from "@/components/RelativeTime";

/**
 * Intro requests in both directions. Incoming ones are the only actionable
 * item on this page, so they carry the buttons and outgoing ones only report
 * their state.
 */
export default function IntrosList() {
    const me = useMe();
    const intros = useMyIntros();
    const respond = useRespondToIntro();
    const myMemberId = me.data?.member_id;

    if (intros.isPending) return <LoadingBlock label="Loading intro requests" rows={2} />;
    if (intros.error) return <ErrorState error={intros.error} onRetry={() => intros.refetch()} />;
    if (!intros.data?.items.length) {
        return (
            <EmptyState
                title="No intro requests"
                hint="When you ask for an intro, or someone asks for one to you, it shows up here."
            />
        );
    }

    return (
        <ul>
            {intros.data.items.map(({ request, requester, target }) => {
                const incoming = request.target_member_id === myMemberId;
                const other = incoming ? requester : target;
                const pending = request.status === "pending";
                // Keyed by the request in flight, so answering one row leaves
                // the buttons on every other row live.
                const busy = respond.isPending && respond.variables?.id === request.id;

                return (
                    <li
                        key={request.id}
                        className="flex items-start gap-3 border-t border-line px-3.5 py-3 first:border-t-0"
                    >
                        <AvatarCircle name={other.name} avatar={avatarOf(other)} px={40} />
                        <div className="min-w-0 flex-1">
                            <p className="text-[13.5px] font-semibold">
                                <Link href={`/members/${other.slug}`} className="hover:text-blue">
                                    {other.name}
                                </Link>
                                <span className="ml-1.5 font-normal text-muted">
                                    {incoming ? "asked for an intro" : "was asked for an intro"}
                                </span>
                            </p>
                            <p className="mt-1 text-[13px] whitespace-pre-line">{request.message}</p>
                            <p className="mt-1 text-[11.5px] text-muted">
                                <RelativeTime value={request.created_at} /> · {request.status}
                            </p>
                        </div>

                        {incoming && pending && (
                            <div className="flex shrink-0 gap-1.5">
                                <button
                                    type="button"
                                    className="btn btn-sm btn-primary"
                                    disabled={busy}
                                    onClick={() => respond.mutate({ id: request.id, status: "accepted" })}
                                >
                                    Accept
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-sm"
                                    disabled={busy}
                                    onClick={() => respond.mutate({ id: request.id, status: "declined" })}
                                >
                                    Decline
                                </button>
                            </div>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}
