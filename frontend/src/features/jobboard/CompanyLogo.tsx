"use client";

import { useState } from "react";

import { initials } from "@/lib/format";

/**
 * A company logo, or its initials.
 *
 * Logo URLs come from whoever posted the job and from a third-party logo host,
 * so a 404 or a DNS failure is normal rather than exceptional. Chrome paints a
 * broken-image glyph for a failed `<img>` even with an empty alt, which looks
 * like a bug on a page of otherwise clean rows, so the failure is caught and
 * the initials underneath are left to stand on their own.
 *
 * That is the only reason this is a client component. It holds one boolean and
 * no effects.
 */
export default function CompanyLogo({
    name,
    logoUrl,
    px = 44,
}: {
    name: string;
    logoUrl?: string | null;
    px?: number;
}) {
    const [failed, setFailed] = useState(false);
    const src = resolve(logoUrl);

    return (
        <span className="logo-box relative" style={{ width: px, height: px }}>
            <span
                aria-hidden="true"
                className="absolute inset-0 grid place-items-center bg-blue-soft text-[13px] font-bold text-blue"
            >
                {initials(name)}
            </span>
            {src && !failed && (
                <img
                    src={src}
                    alt=""
                    width={px}
                    height={px}
                    loading="lazy"
                    decoding="async"
                    onError={() => setFailed(true)}
                    className="absolute inset-0 h-full w-full bg-white object-contain p-1.5"
                />
            )}
        </span>
    );
}

/** Dev seeds point at localhost; strip the origin so they load same-origin. */
function resolve(logoUrl: string | null | undefined): string | null {
    if (!logoUrl) return null;
    if (logoUrl.startsWith("/")) return logoUrl;
    try {
        const url = new URL(logoUrl);
        if (url.hostname === "localhost" || url.hostname === "127.0.0.1") {
            return `${url.pathname}${url.search}`;
        }
        return url.protocol === "http:" || url.protocol === "https:" ? logoUrl : null;
    } catch {
        return null;
    }
}
