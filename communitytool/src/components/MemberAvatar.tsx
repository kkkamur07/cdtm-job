import type { Avatar } from "@/lib/types";

/**
 * About 40% of members have no CMS photo, so the fallback is not an edge case
 * — it has to read as a deliberate state rather than a broken image.
 *
 * The initials are drawn as SVG text inside a fixed viewBox, so they scale
 * exactly with the tile at any browser zoom, any breakpoint, and any DPR.
 * A font-size in px would need a breakpoint for every tile width.
 */

const TINTS = [
    { bg: "#e5eaf4", fg: "#183e8e" }, // blue-soft
    { bg: "#f0f6da", fg: "#5c6f16" }, // green-soft
    { bg: "#f6f6f4", fg: "#4a4a4a" }, // cream
];

function initials(name: string): string {
    const parts = name.split(/\s+/).filter((p) => /[a-zA-Z\u00C0-\u024F]/.test(p));
    if (!parts.length) return "?";
    const first = parts[0][0] ?? "";
    const last = parts.length > 1 ? (parts[parts.length - 1][0] ?? "") : "";
    return (first + last).toUpperCase();
}

/** Stable per-name tint, so a wall of fallbacks has texture but never flickers. */
function tintFor(seed: string) {
    let h = 0;
    for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
    return TINTS[Math.abs(h) % TINTS.length];
}

export default function MemberAvatar({
                                         name,
                                         avatar,
                                         size,
                                         priority = false,
                                     }: {
    name: string;
    avatar: Avatar | null;
    /** Which rendition to pull: tiles use `sm` (360px), the modal uses `lg`. */
    size: "sm" | "lg";
    /** Above-the-fold tiles: fetch immediately at high priority, never lazily. */
    priority?: boolean;
}) {
    const src = avatar?.[size] ?? null;

    if (avatar && src) {
        const px = size === "sm" ? 360 : 400;
        return (
            // The placeholder is the background of the <img> ITSELF, not of a
            // wrapper. With two elements the browser composites two layers and the
            // handover between them can land on a frame boundary — that is the
            // one-frame flash. One element means the decoded photo simply paints
            // over its own background, in the same layer, in the same frame.
            //
            // decoding="sync" for the same reason: "async" explicitly permits
            // presenting the element before its bitmap is ready, which is what
            // splits the swap across two frames. These are ~8KB, so decoding them
            // inline costs well under a millisecond.
            //
            // There is deliberately NO fade. A per-image transition only plays for
            // photos actually mid-flight, so a filtered grid showed some tiles
            // fading and some appearing instantly, and that mismatch reads worse
            // than either behaviour alone.
            <img
                src={src}
                alt=""
                loading={priority ? "eager" : "lazy"}
                fetchPriority={priority ? "high" : "auto"}
                decoding="sync"
                width={px}
                height={px}
                className="h-full w-full object-cover"
                style={
                    avatar.blur
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
        <svg viewBox="0 0 100 100" className="h-full w-full" role="presentation" aria-hidden="true">
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