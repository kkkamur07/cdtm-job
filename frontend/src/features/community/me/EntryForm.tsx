"use client";

import { useState } from "react";

import { useMyEntry, useSaveMyEntry } from "@/api/hooks/me";
import type { ContactPreference, EntryUpsert, Visibility } from "@/api/types";
import Field, { FieldRow } from "@/components/Field";
import { FormError } from "@/components/states";
import { LoadingBlock } from "@/components/placeholders";
import { joinList, parseList } from "@/lib/format";
import { focusFirstInvalid } from "@/lib/forms";

const CONTACT: { value: ContactPreference; label: string }[] = [
    { value: "intro", label: "Ask for an intro first" },
    { value: "email", label: "Email me directly" },
    { value: "linkedin", label: "Message me on LinkedIn" },
];

type FormState = {
    about: string;
    ask_me_about: string;
    current_title: string;
    current_company: string;
    location: string;
    topics: string;
    hobbies: string;
    contact_email: string;
    contact_preference: ContactPreference;
    visibility: Visibility;
};

const BLANK: FormState = {
    about: "",
    ask_me_about: "",
    current_title: "",
    current_company: "",
    location: "",
    topics: "",
    hobbies: "",
    contact_email: "",
    contact_preference: "intro",
    visibility: "members",
};

/**
 * The part of a member entry the member writes themselves. Everything else on
 * their profile comes from the roster and LinkedIn, and is not editable here:
 * this form is only the additions.
 */
export default function EntryForm() {
    const entry = useMyEntry();
    if (entry.isPending) return <LoadingBlock label="Loading your entry" rows={4} />;

    // The fields mount only once the server value is in hand, so the form is
    // seeded by its initial state rather than corrected by an effect after the
    // first paint.
    return <EntryFields initial={toFormState(entry.data)} />;
}

function toFormState(entry: ReturnType<typeof useMyEntry>["data"]): FormState {
    if (!entry) return BLANK;
    return {
        about: entry.about ?? "",
        ask_me_about: entry.ask_me_about ?? "",
        current_title: entry.current_title ?? "",
        current_company: entry.current_company ?? "",
        location: entry.location ?? "",
        topics: joinList(entry.topics),
        hobbies: joinList(entry.hobbies),
        contact_email: entry.contact_email ?? "",
        contact_preference: entry.contact_preference ?? "intro",
        visibility: entry.visibility ?? "members",
    };
}

function EntryFields({ initial }: { initial: FormState }) {
    const save = useSaveMyEntry();
    const [form, setForm] = useState<FormState>(initial);

    const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
        setForm((prev) => ({ ...prev, [key]: value }));

    const submit = (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        // Nothing here is required, so the only thing that can fail is the
        // contact email. Focusing it beats a silent no-op on submit.
        if (!focusFirstInvalid(event.currentTarget)) return;

        const body: EntryUpsert = {
            about: form.about.trim() || null,
            ask_me_about: form.ask_me_about.trim() || null,
            current_title: form.current_title.trim() || null,
            current_company: form.current_company.trim() || null,
            location: form.location.trim() || null,
            topics: parseList(form.topics),
            hobbies: parseList(form.hobbies),
            contact_email: form.contact_email.trim() || null,
            contact_preference: form.contact_preference,
            visibility: form.visibility,
        };
        save.mutate(body);
    };

    return (
        <form className="grid gap-4" onSubmit={submit}>
            <Field label="Ask me about" hint="The one line people should read before reaching out.">
                {(props) => (
                    <input
                        {...props}
                        className="input"
                        value={form.ask_me_about}
                        onChange={(event) => set("ask_me_about", event.target.value)}
                        placeholder="Scaling ops past 500 people, car subscription unit economics"
                    />
                )}
            </Field>

            <Field label="About">
                {(props) => (
                    <textarea
                        {...props}
                        className="textarea"
                        value={form.about}
                        onChange={(event) => set("about", event.target.value)}
                    />
                )}
            </Field>

            <FieldRow>
                <Field label="Current title">
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={form.current_title}
                            onChange={(event) => set("current_title", event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Current company">
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={form.current_company}
                            onChange={(event) => set("current_company", event.target.value)}
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
                            placeholder="Munich, Germany"
                        />
                    )}
                </Field>
                <Field label="Contact email" hint="Only shown if you pick email below.">
                    {(props) => (
                        <input
                            {...props}
                            type="email"
                            className="input"
                            value={form.contact_email}
                            onChange={(event) => set("contact_email", event.target.value)}
                        />
                    )}
                </Field>
            </FieldRow>

            <FieldRow>
                <Field label="Topics" hint="Comma separated.">
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={form.topics}
                            onChange={(event) => set("topics", event.target.value)}
                            placeholder="Fundraising, GovTech, EU AI Act"
                        />
                    )}
                </Field>
                <Field label="Outside work" hint="Comma separated.">
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={form.hobbies}
                            onChange={(event) => set("hobbies", event.target.value)}
                            placeholder="Climbing, chess"
                        />
                    )}
                </Field>
            </FieldRow>

            <FieldRow>
                <Field label="How to reach you">
                    {(props) => (
                        <select
                            {...props}
                            className="select"
                            value={form.contact_preference}
                            onChange={(event) =>
                                set("contact_preference", event.target.value as ContactPreference)
                            }
                        >
                            {CONTACT.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    )}
                </Field>
                <Field label="Visibility" hint="Hidden keeps you out of search results.">
                    {(props) => (
                        <select
                            {...props}
                            className="select"
                            value={form.visibility}
                            onChange={(event) => set("visibility", event.target.value as Visibility)}
                        >
                            <option value="members">Visible to members</option>
                            <option value="hidden">Hidden</option>
                        </select>
                    )}
                </Field>
            </FieldRow>

            <FormError error={save.error} />

            <div className="flex items-center gap-3">
                <button type="submit" className="btn btn-primary" disabled={save.isPending}>
                    {save.isPending ? "Saving…" : "Save entry"}
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
