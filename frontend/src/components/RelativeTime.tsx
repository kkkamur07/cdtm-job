"use client";

import { useSyncExternalStore } from "react";

import { formatDate, timeAgo } from "@/lib/format";

/**
 * "3 days ago", without the hydration mismatch.
 *
 * `timeAgo` reads the clock, and the server's clock and the browser's are not
 * the same instant. Around midnight one says "Yesterday" and the other says
 * "Today", React notices, and the text visibly changes after load. So the
 * server and the first client render both print the fixed date, which cannot
 * disagree, and the relative wording is swapped in after hydration, where only
 * the browser's clock is involved.
 *
 * `useSyncExternalStore` is how that switch is read rather than a state update
 * in an effect: it has a server snapshot built in, so there is one render on
 * the server and one after hydration, not a cascade.
 *
 * The full date stays in `title` and the machine-readable instant in
 * `dateTime`, so the exact moment is always recoverable.
 */

const noop = () => () => {};
const onClient = () => true;
const onServer = () => false;

export default function RelativeTime({ value }: { value: string | null | undefined }) {
    const hydrated = useSyncExternalStore(noop, onClient, onServer);

    const absolute = formatDate(value);
    if (!value || !absolute) return null;

    return (
        <time dateTime={value} title={absolute}>
            {hydrated ? (timeAgo(value) ?? absolute) : absolute}
        </time>
    );
}
