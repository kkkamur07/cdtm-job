"use client";

import { useState } from "react";

import { useMyIntros, useRequestIntro } from "@/api/hooks/me";
import { FormError } from "@/components/states";
import { firstName } from "@/lib/format";

/**
 * Asking for an introduction. Collapsed to a button until it is wanted, because
 * an always-open textarea on every profile reads as an obligation.
 *
 * A request that is already pending shows its state instead of the form: the
 * useful thing to know at that point is that you already asked.
 */
export default function IntroRequest({ memberId, name }: { memberId: string; name: string }) {
    const [open, setOpen] = useState(false);
    const [message, setMessage] = useState("");
    // Narrowed to this member on the server: a row or none, rather than the
    // whole history cut at a page and searched here, which said "never asked"
    // about anyone whose request had fallen off the end of it.
    const intros = useMyIntros(memberId);
    const request = useRequestIntro();

    // Both directions come back, so the outgoing one is picked out by target.
    const existing = intros.data?.items.find(
        (intro) => intro.request.target_member_id === memberId && intro.request.status === "pending",
    );

    if (existing) {
        return (
            <p className="rounded-2xl bg-cream px-3.5 py-2.5 text-[12.5px] text-muted">
                Intro request sent. {firstName(name)} has not responded yet.
            </p>
        );
    }

    if (request.isSuccess) {
        return (
            <p className="rounded-2xl bg-green-soft px-3.5 py-2.5 text-[12.5px]">
                Sent. {firstName(name)} will see your request in their inbox.
            </p>
        );
    }

    if (!open) {
        return (
            <button type="button" className="btn btn-sm" onClick={() => setOpen(true)}>
                Request intro
            </button>
        );
    }

    return (
        <form
            className="grid gap-2"
            onSubmit={(event) => {
                event.preventDefault();
                if (!message.trim()) return;
                request.mutate({ target_member_id: memberId, message: message.trim() });
            }}
        >
            <label className="label" htmlFor={`intro-${memberId}`}>
                Why you are reaching out
            </label>
            <textarea
                id={`intro-${memberId}`}
                className="textarea"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                required
                placeholder={`I am working on … and would love 20 minutes with ${firstName(name)} about …`}
            />
            <FormError error={request.error} />
            <div className="flex gap-2">
                <button
                    type="submit"
                    className="btn btn-sm btn-blue"
                    disabled={request.isPending || !message.trim()}
                >
                    {request.isPending ? "Sending…" : "Send request"}
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setOpen(false)}>
                    Cancel
                </button>
            </div>
        </form>
    );
}
