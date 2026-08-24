"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCreateEvent } from "@/api/hooks/community";
import type { EventKind } from "@/api/types";
import Field, { FieldRow } from "@/components/Field";
import Panel from "@/components/Panel";
import { FormError } from "@/components/states";
const KINDS: { value: EventKind; label: string }[] = [
    { value: "cdtm", label: "CDTM" },
    { value: "community", label: "Community" },
    { value: "external", label: "External" },
];

export default function NewEventForm() {
    const router = useRouter();
    const create = useCreateEvent();
    const [form, setForm] = useState({
        title: "",
        starts_at: "",
        ends_at: "",
        location: "",
        url: "",
        description: "",
        kind: "community" as EventKind,
    });

    const set = (key: keyof typeof form, value: string) =>
        setForm((prev) => ({ ...prev, [key]: value }));

    const submit = (event: React.FormEvent) => {
        event.preventDefault();
        create.mutate(
            {
                title: form.title.trim(),
                // datetime-local has no zone; treating it as local time is what
                // the person typing it means.
                starts_at: new Date(form.starts_at).toISOString(),
                ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
                location: form.location.trim() || null,
                url: form.url.trim() || null,
                description: form.description.trim() || null,
                kind: form.kind,
                is_published: true,
            },
            { onSuccess: (created) => router.push(`/events/${created.id}`) },
        );
    };

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <Link href="/events" className="w-fit text-[12.5px] font-medium text-blue hover:underline">
                Back to events
            </Link>

            <Panel title="Add an event">
                <form className="grid gap-4" onSubmit={submit}>
                    <Field label="Title" required>
                        {(props) => (
                            <input
                                {...props}
                                className="input"
                                required
                                value={form.title}
                                onChange={(event) => set("title", event.target.value)}
                            />
                        )}
                    </Field>

                    <FieldRow>
                        <Field label="Starts" required>
                            {(props) => (
                                <input
                                    {...props}
                                    type="datetime-local"
                                    className="input"
                                    required
                                    value={form.starts_at}
                                    onChange={(event) => set("starts_at", event.target.value)}
                                />
                            )}
                        </Field>
                        <Field label="Ends">
                            {(props) => (
                                <input
                                    {...props}
                                    type="datetime-local"
                                    className="input"
                                    value={form.ends_at}
                                    onChange={(event) => set("ends_at", event.target.value)}
                                />
                            )}
                        </Field>
                    </FieldRow>

                    <FieldRow>
                        <Field label="Location">
                            {(props) => (
                                <input
                                    {...props}
                                    className="input"
                                    value={form.location}
                                    onChange={(event) => set("location", event.target.value)}
                                    placeholder="CDTM, Munich"
                                />
                            )}
                        </Field>
                        <Field label="Kind">
                            {(props) => (
                                <select
                                    {...props}
                                    className="select"
                                    value={form.kind}
                                    onChange={(event) => set("kind", event.target.value)}
                                >
                                    {KINDS.map((kind) => (
                                        <option key={kind.value} value={kind.value}>
                                            {kind.label}
                                        </option>
                                    ))}
                                </select>
                            )}
                        </Field>
                    </FieldRow>

                    <Field label="Link" hint="Tickets, sign-up or a page with the details.">
                        {(props) => (
                            <input
                                {...props}
                                type="url"
                                className="input"
                                value={form.url}
                                onChange={(event) => set("url", event.target.value)}
                                placeholder="https://"
                            />
                        )}
                    </Field>

                    <Field label="Description">
                        {(props) => (
                            <textarea
                                {...props}
                                className="textarea"
                                value={form.description}
                                onChange={(event) => set("description", event.target.value)}
                            />
                        )}
                    </Field>

                    <FormError error={create.error} />

                    <div className="flex gap-2">
                        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                            {create.isPending ? "Publishing…" : "Publish event"}
                        </button>
                        <Link href="/events" className="btn btn-ghost">
                            Cancel
                        </Link>
                    </div>
                </form>
            </Panel>
        </div>
    );
}
