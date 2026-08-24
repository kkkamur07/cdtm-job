"use client";

import { useMySaved, useToggleSaved } from "@/api/hooks/me";
import { toNetworkMember } from "@/api/people";
import type { Member } from "@/api/types";

function BookmarkIcon({ filled }: { filled: boolean }) {
    return (
        <svg width="13" height="13" viewBox="0 0 16 16" fill={filled ? "currentColor" : "none"} aria-hidden="true">
            <path
                d="M4 2.5h8v11l-4-2.6-4 2.6z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
            />
        </svg>
    );
}

/**
 * Save / unsave a member. The saved list is small (it is a personal shortlist,
 * not a follow graph), so it is fetched once and read from the cache here
 * rather than every row asking the server whether it is saved.
 *
 * `member` is passed where the caller has it so the shortlist can show the new
 * row before the write comes back. Without it the toggle still works; the list
 * simply catches up a moment later.
 */
export default function SaveButton({
    memberId,
    member,
    label = true,
}: {
    memberId: string;
    member?: Member;
    label?: boolean;
}) {
    const saved = useMySaved();
    const toggle = useToggleSaved();
    const isSaved = Boolean(saved.data?.some((s) => s.saved.saved_member_id === memberId));
    // Keyed by the member the write is for, so one row in flight never greys
    // out the rest of the list.
    const busy = toggle.isPending && toggle.variables?.memberId === memberId;

    return (
        <button
            type="button"
            className={`btn btn-sm ${isSaved ? "border-green bg-green-soft" : ""}`}
            aria-pressed={isSaved}
            disabled={busy || saved.isPending}
            onClick={(event) => {
                event.stopPropagation();
                toggle.mutate({
                    memberId,
                    saved: !isSaved,
                    member: member && toNetworkMember(member),
                });
            }}
        >
            <BookmarkIcon filled={isSaved} />
            {label && (isSaved ? "Saved" : "Save")}
            {!label && <span className="sr-only">{isSaved ? "Remove from saved" : "Save this person"}</span>}
        </button>
    );
}
