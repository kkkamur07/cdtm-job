"use client";

import { useSavedIds, useToggleSaved } from "@/api/hooks/me";
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
 * Save / unsave a member.
 *
 * Membership comes from `useSavedIds`, which is the whole shortlist as ids and
 * unpaged, so every button on a results page is drawn from one cached set
 * rather than each row asking the server. It is deliberately not the display
 * page: that is cut at a hundred rows, and a button reading its own state off
 * it drew somebody already saved as unsaved.
 *
 * No note is passed. This button knows nothing about the note on the row, so it
 * says nothing about it and the server keeps whatever is there.
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
    const saved = useSavedIds();
    const toggle = useToggleSaved();
    const isSaved = saved.data?.has(memberId) ?? false;
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
