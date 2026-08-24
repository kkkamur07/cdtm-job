"use client";

import { useState } from "react";

import { useMyIntents, useSaveMyIntents } from "@/api/hooks/me";
import type { IntentsUpsert } from "@/api/types";
import { FormError } from "@/components/states";
import { LoadingBlock } from "@/components/placeholders";
import { INTENTS, type IntentKey } from "@/lib/intents";

type State = Record<IntentKey, boolean>;

const BLANK: State = {
    cofounding: false,
    mentoring: false,
    hiring: false,
    open_to_roles: false,
    investing: false,
    speaking: false,
};

/**
 * What you are open to. These are the filters other members search by, so this
 * form is the single highest-value thing a member can fill in: switches rather
 * than checkboxes, because the state has to be readable across the room.
 */
export default function IntentsForm() {
    const intents = useMyIntents();
    if (intents.isPending) return <LoadingBlock label="Loading your intents" rows={3} />;

    // Mounted with the server value already in hand, so the switches never
    // flip under the reader a frame after they render.
    const initial = { ...BLANK };
    for (const intent of INTENTS) initial[intent.key] = Boolean(intents.data?.[intent.key]);
    return <IntentSwitches initial={initial} initialNote={intents.data?.note ?? ""} />;
}

function IntentSwitches({ initial, initialNote }: { initial: State; initialNote: string }) {
    const save = useSaveMyIntents();
    const [state, setState] = useState<State>(initial);
    const [note, setNote] = useState(initialNote);

    const submit = (event: React.FormEvent) => {
        event.preventDefault();
        const body: IntentsUpsert = { ...state, note: note.trim() || null };
        save.mutate(body);
    };

    return (
        <form className="grid gap-4" onSubmit={submit}>
            <ul className="grid gap-2">
                {INTENTS.map((intent) => {
                    const on = state[intent.key];
                    return (
                        <li key={intent.key}>
                            {/* The real checkbox is visually hidden and the
                                switch beside it is decorative, so focus lands
                                on something nobody can see. `peer-focus-visible`
                                puts the ring back on the row that is actually
                                focused. */}
                            <label
                                className={`flex cursor-pointer items-center gap-3 rounded-2xl border px-3 py-2.5 transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-blue ${
                                    on ? "border-blue bg-blue-soft" : "border-line bg-white"
                                }`}
                            >
                                <input
                                    type="checkbox"
                                    className="peer sr-only"
                                    checked={on}
                                    onChange={(event) =>
                                        setState((prev) => ({ ...prev, [intent.key]: event.target.checked }))
                                    }
                                />
                                <span
                                    aria-hidden="true"
                                    className={`relative h-5 w-[34px] shrink-0 rounded-[var(--radius-pill)] transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-blue peer-focus-visible:ring-offset-2 ${
                                        on ? "bg-blue" : "bg-line"
                                    }`}
                                >
                                    <span
                                        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-[left] ${
                                            on ? "left-4" : "left-0.5"
                                        }`}
                                    />
                                </span>
                                <span>
                                    <span className="block text-[13.5px] font-semibold">{intent.label}</span>
                                    <span className="block text-xs text-muted">{intent.description}</span>
                                </span>
                            </label>
                        </li>
                    );
                })}
            </ul>

            <div>
                <label className="label" htmlFor="intents-note">
                    Anything to add
                </label>
                <textarea
                    id="intents-note"
                    className="textarea"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Specifically looking for a technical co-founder for a climate hardware idea."
                />
            </div>

            <FormError error={save.error} />

            <div className="flex items-center gap-3">
                <button type="submit" className="btn btn-primary" disabled={save.isPending}>
                    {save.isPending ? "Saving…" : "Save what I am open to"}
                </button>
                {save.isSuccess && !save.isPending && (
                    <span role="status" className="text-[12.5px] text-muted">
                        Saved.
                    </span>
                )}
            </div>
        </form>
    );
}
