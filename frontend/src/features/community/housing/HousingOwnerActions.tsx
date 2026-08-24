"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useRenewHousing, useUpdateHousing } from "@/api/hooks/community";
import { FormError } from "@/components/states";

/**
 * The owner's controls on their own listing.
 *
 * Two things an owner needs and nobody else does: keep it alive, or take it
 * down. Both are real calls now that listings carry an expiry, and both refresh
 * the server-rendered page afterwards so the panel above them tells the truth.
 *
 * `daysLeft` arrives already worked out. Reading the clock while rendering puts
 * the server and the browser on possibly different sides of a day boundary, and
 * the countdown would then rewrite itself a moment after the page appears.
 *
 * Views and message counts are not shown because the API does not count them.
 */
export default function HousingOwnerActions({
    id,
    closed,
    posted,
    daysLeft,
}: {
    id: string;
    closed: boolean;
    posted: string | null;
    /** Whole days until the listing expires, or null if it has no expiry. */
    daysLeft: number | null;
}) {
    const router = useRouter();
    const update = useUpdateHousing(id);
    const renew = useRenewHousing(id);
    const [confirmingClose, setConfirmingClose] = useState(false);

    const busy = update.isPending || renew.isPending;
    const after = () => router.refresh();

    const setStatus = (status: "open" | "closed") => {
        setConfirmingClose(false);
        update.mutate({ status }, { onSuccess: after });
    };

    return (
        <div className="card panel owner">
            <h2 className="label">Your listing</h2>
            <p className="mt-1.5 text-[13px]">
                {closed ? "Closed" : "Live"}
                {posted ? ` since ${posted}` : ""}. Only you can edit it.
            </p>

            {!closed && daysLeft !== null && (
                <p className={`mt-1.5 text-[13px] ${daysLeft <= 7 ? "text-ink" : "text-muted"}`}>
                    {daysLeft <= 0
                        ? "Expired, so it is off the board. Renew to put it back."
                        : daysLeft === 1
                          ? "Expires tomorrow."
                          : `Expires in ${daysLeft} days.`}
                </p>
            )}

            <Link href={`/housing/${id}/edit`} className="btn btn-primary mt-3.5 w-full">
                Edit listing
            </Link>

            <div className="mt-2 flex gap-2">
                <button
                    type="button"
                    className="btn flex-1"
                    disabled={busy}
                    onClick={() => renew.mutate(undefined, { onSuccess: after })}
                >
                    {renew.isPending ? "Renewing…" : "Renew for 60 days"}
                </button>

                {/* Closing takes the listing off the board for everyone else, so
                    it asks first. Reopening is harmless and does not. */}
                {closed ? (
                    <button
                        type="button"
                        className="btn flex-1"
                        disabled={busy}
                        onClick={() => setStatus("open")}
                    >
                        Reopen
                    </button>
                ) : confirmingClose ? (
                    <span className="flex flex-1 gap-2">
                        <button
                            type="button"
                            className="btn flex-1"
                            disabled={busy}
                            onClick={() => setStatus("closed")}
                        >
                            {update.isPending ? "Closing…" : "Yes, close it"}
                        </button>
                        <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => setConfirmingClose(false)}
                        >
                            Keep it open
                        </button>
                    </span>
                ) : (
                    <button
                        type="button"
                        className="btn flex-1"
                        disabled={busy}
                        onClick={() => setConfirmingClose(true)}
                    >
                        Mark as closed
                    </button>
                )}
            </div>

            {closed && (
                <p className="mt-2 text-[12px] text-muted">
                    Closed by mistake? Reopen puts it straight back on the board.
                </p>
            )}

            {(update.error || renew.error) && (
                <div className="mt-2.5">
                    <FormError error={update.error ?? renew.error} />
                </div>
            )}
        </div>
    );
}
