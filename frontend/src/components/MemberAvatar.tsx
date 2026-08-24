import type { Avatar } from "@/api/types";
import { initials } from "@/lib/format";

/**
 * About 40% of members have no CMS photo, so the fallback is not an edge case:
 * it has to read as a deliberate state rather than a broken image.
 *
 * The initials are drawn as SVG text inside a fixed viewBox, so they scale
 * exactly with the container at any zoom, breakpoint and DPR. A font-size in
 * px would need a breakpoint for every avatar size.
 *
 * `avatar.sm` / `avatar.lg` may be a path served from public/ (what ingest
 * writes today) or an absolute URL once avatars move to storage. Both work
 * unchanged as an <img src>, so nothing here rewrites them.
 */

const TINTS = [
    { bg: "#e5eaf4", fg: "#183e8e" },
    { bg: "#f0f6da", fg: "#5c6f16" },
    { bg: "#f6f6f4", fg: "#4a4a4a" },
];

/** Stable per-name tint, so a wall of fallbacks has texture but never flickers. */
function tintFor(seed: string) {
    let h = 0;
    for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
    return TINTS[Math.abs(h) % TINTS.length];
}

export default function MemberAvatar({
    name,
    avatar,
    size = "sm",
    priority = false,
    className = "",
}: {
    name: string;
    avatar?: Avatar | null;
    /** Which rendition to pull: lists use `sm` (160px), detail views use `lg`. */
    size?: "sm" | "lg";
    /** Above-the-fold: fetch immediately, never lazily. */
    priority?: boolean;
    className?: string;
}) {
    const src = avatar?.[size] ?? null;

    if (src) {
        return (
            // The placeholder is the background of the <img> ITSELF, not of a
            // wrapper: with two elements the handover between them can land on a
            // frame boundary, which is the one-frame flash.
            <img
                src={src}
                alt=""
                loading={priority ? "eager" : "lazy"}
                fetchPriority={priority ? "high" : "auto"}
                decoding="sync"
                width={size === "sm" ? 160 : 400}
                height={size === "sm" ? 160 : 400}
                className={`h-full w-full object-cover ${className}`}
                style={
                    avatar?.blur
                        ? {
                              backgroundImage: `url("${avatar.blur}")`,
                              backgroundSize: "cover",
                              backgroundPosition: "center",
                          }
                        : undefined
                }
            />
        );
    }

    const tint = tintFor(name);
    return (
        <svg
            viewBox="0 0 100 100"
            className={`h-full w-full ${className}`}
            role="presentation"
            aria-hidden="true"
        >
            <rect width="100" height="100" fill={tint.bg} />
            <text
                x="50"
                y="50"
                fill={tint.fg}
                fontSize="34"
                fontWeight="600"
                letterSpacing="-1"
                textAnchor="middle"
                dominantBaseline="central"
                fontFamily="inherit"
            >
                {initials(name)}
            </text>
        </svg>
    );
}

/** Circular avatar at a fixed pixel size, the shape used in lists and rails. */
export function AvatarCircle({
    name,
    avatar,
    px = 44,
    size = "sm",
}: {
    name: string;
    avatar?: Avatar | null;
    px?: number;
    size?: "sm" | "lg";
}) {
    return (
        <span
            className="block shrink-0 overflow-hidden rounded-full bg-cream"
            style={{ width: px, height: px }}
        >
            <MemberAvatar name={name} avatar={avatar} size={size} />
        </span>
    );
}
