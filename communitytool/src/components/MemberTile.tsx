"use client";

import type { Member } from "@/lib/types";
import MemberAvatar from "./MemberAvatar";

/**
 * One person in the grid.
 *
 * Every zone below the photo has a FIXED height, not an intrinsic one. That's
 * what keeps the grid aligned: names run from one word to five, subtitles are
 * often missing, and roughly a third of members have no class pill. If those
 * zones sized to their content, each row would settle at the height of its
 * tallest card and the text would sit at a different height in every tile.
 *
 *   photo    square, full-bleed
 *   name     1 line, truncated       20px
 *   role     1 line, truncated       16px
 *   pills    fixed row               20px
 *
 * The name is ONE line, not two. Allowing two meant reserving 40px for a zone
 * that usually held 20, and that reserved-but-empty half-line was the gap
 * sitting above the class pill. At one line every zone is always full, so the
 * block is tight AND the pill lands on the same baseline in every tile.
 *
 * The role keeps a non-breaking space when absent — 16px is a small price for
 * the pill row never drifting, and roughly a third of members have no role.
 * The full name is on the button's title attribute when it truncates.
 */
export default function MemberTile({
                                       member,
                                       onOpen,
                                       onPrefetch,
                                       busy = false,
                                       priority = false,
                                   }: {
    member: Member;
    onOpen: (id: string) => void;
    /** Warms the profile JSON and portrait before the click lands. */
    onPrefetch?: (id: string, avatarLg?: string | null) => void;
    busy?: boolean;
    /** True for the first rows, which must not wait on the lazy-load observer. */
    priority?: boolean;
}) {
    const warm = () => onPrefetch?.(member.id, member.avatar?.lg);
    const subtitle =
        member.title && member.company
            ? `${member.title}, ${member.company}`
            : (member.title ?? member.company ?? member.headline);

    return (
        <button
            type="button"
            onClick={() => onOpen(member.id)}
            onPointerEnter={warm}
            onPointerDown={warm}
            onFocus={warm}
            title={member.name}
            aria-busy={busy || undefined}
            className={`card group flex flex-col overflow-hidden p-0 text-left transition-[transform,box-shadow,border-color,opacity] duration-150 hover:-translate-y-0.5 hover:border-blue/25 hover:shadow-[0_4px_18px_rgb(24_62_142/0.09)] ${
                busy ? "opacity-60" : ""
            }`}
        >
            <div className="aspect-square w-full overflow-hidden border-b border-line bg-cream">
                <MemberAvatar name={member.name} avatar={member.avatar} size="sm" priority={priority} />
            </div>

            <div className="flex flex-col p-3">
                <h2 className="truncate text-[13px] leading-5 font-semibold tracking-tight">
                    {member.name}
                </h2>

                <p className="truncate text-[11px] leading-4 text-muted">
                    {subtitle ?? "\u00A0"}
                </p>

                <div className="mt-1.5 flex h-5 items-center gap-1 overflow-hidden">
                    {member.classLabel && (
                        <span className="shrink-0 rounded-[var(--radius-pill)] bg-blue-soft px-1.5 py-[3px] text-[10px] leading-none font-medium text-blue">
              {member.classLabel}
            </span>
                    )}
                    {member.isCA && (
                        <span
                            className="shrink-0 rounded-[var(--radius-pill)] bg-green px-1.5 py-[3px] text-[10px] leading-none font-semibold text-ink"
                            title={
                                member.caAlumni === false
                                    ? "Current Center Assistant"
                                    : "Former Center Assistant"
                            }
                        >
              CA
            </span>
                    )}
                </div>
            </div>
        </button>
    );
}