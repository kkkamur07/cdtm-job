"use client";

import type { MemberProfile, SelfProfileCreate } from "@/api/types";
import Field, { FieldRow } from "@/components/Field";

/**
 * The one profile form, shared by create (onboarding) and edit (your account).
 *
 * The fields are the same in both directions, so an imported member who just
 * signed in and a self-created one maintain exactly the same things. Only the
 * surrounding heading, the submit label and what happens on success differ, so
 * those stay with each caller and everything below is shared.
 */
export type ProfileFormState = {
    name: string;
    class_id: string;
    major: string;
    headline: string;
    current_company: string;
    current_title: string;
    location: string;
    linkedin_url: string;
    summary: string;
};

export const emptyProfileForm: ProfileFormState = {
    name: "",
    class_id: "",
    major: "",
    headline: "",
    current_company: "",
    current_title: "",
    location: "",
    linkedin_url: "",
    summary: "",
};

/** Fill the form from an existing profile, for the edit path. */
export function profileFromMember(member: MemberProfile): ProfileFormState {
    return {
        name: member.name ?? "",
        // A member can sit in more than one class; the first is the one the card leads with.
        class_id: member.classes?.[0]?.id != null ? String(member.classes[0].id) : "",
        major: member.major ?? "",
        headline: member.headline ?? "",
        current_company: member.company ?? "",
        current_title: member.title ?? "",
        location: member.location ?? "",
        linkedin_url: member.linkedin_url ?? "",
        summary: member.summary ?? "",
    };
}

/** Turn the form into the API payload, trimming and nulling the empty optionals. */
export function toProfilePayload(form: ProfileFormState): SelfProfileCreate {
    return {
        name: form.name.trim(),
        class_id: Number(form.class_id),
        major: form.major.trim(),
        headline: form.headline.trim() || null,
        current_company: form.current_company.trim() || null,
        current_title: form.current_title.trim() || null,
        location: form.location.trim() || null,
        linkedin_url: form.linkedin_url.trim() || null,
        summary: form.summary.trim() || null,
    };
}

type ClassOption = { id: number; label: string };

/**
 * Just the fields, in a `<form>`. The caller owns the state, the submit
 * handler and the button, so the same body works for create and edit.
 */
export function ProfileFormBody({
    form,
    set,
    classes,
    majors,
    classesLoading,
    onSubmit,
    children,
}: {
    form: ProfileFormState;
    set: (key: keyof ProfileFormState, value: string) => void;
    classes: ClassOption[];
    majors: string[];
    classesLoading: boolean;
    onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
    /** The error banner and submit row, which differ between create and edit. */
    children: React.ReactNode;
}) {
    return (
        <form onSubmit={onSubmit} noValidate className="card flex flex-col gap-4 p-5">
            <Field label="Full name" required>
                {(props) => (
                    <input
                        {...props}
                        name="name"
                        className="input"
                        value={form.name}
                        onChange={(e) => set("name", e.target.value)}
                        maxLength={160}
                        autoComplete="name"
                    />
                )}
            </Field>

            <FieldRow>
                <Field label="Class" required hint="Which batch you belong to.">
                    {(props) => (
                        <select
                            {...props}
                            name="class_id"
                            className="select"
                            value={form.class_id}
                            onChange={(e) => set("class_id", e.target.value)}
                            required
                        >
                            <option value="" disabled>
                                {classesLoading ? "Loading…" : "Select your class"}
                            </option>
                            {classes.map((c) => (
                                <option key={c.id} value={c.id}>
                                    {c.label}
                                </option>
                            ))}
                        </select>
                    )}
                </Field>
                <Field label="Study" required hint="Your degree or field.">
                    {(props) => (
                        <input
                            {...props}
                            name="major"
                            className="input"
                            value={form.major}
                            onChange={(e) => set("major", e.target.value)}
                            list="profile-majors"
                            maxLength={160}
                        />
                    )}
                </Field>
            </FieldRow>
            <datalist id="profile-majors">
                {majors.map((m) => (
                    <option key={m} value={m} />
                ))}
            </datalist>

            <Field label="Headline" hint="One line, e.g. what you are working on.">
                {(props) => (
                    <input
                        {...props}
                        name="headline"
                        className="input"
                        value={form.headline}
                        onChange={(e) => set("headline", e.target.value)}
                        maxLength={200}
                    />
                )}
            </Field>

            <FieldRow>
                <Field label="Current company">
                    {(props) => (
                        <input
                            {...props}
                            name="current_company"
                            className="input"
                            value={form.current_company}
                            onChange={(e) => set("current_company", e.target.value)}
                            maxLength={160}
                            autoComplete="organization"
                        />
                    )}
                </Field>
                <Field label="Current title">
                    {(props) => (
                        <input
                            {...props}
                            name="current_title"
                            className="input"
                            value={form.current_title}
                            onChange={(e) => set("current_title", e.target.value)}
                            maxLength={160}
                            autoComplete="organization-title"
                        />
                    )}
                </Field>
            </FieldRow>

            <FieldRow>
                <Field label="Location">
                    {(props) => (
                        <input
                            {...props}
                            name="location"
                            className="input"
                            value={form.location}
                            onChange={(e) => set("location", e.target.value)}
                            maxLength={160}
                            autoComplete="address-level2"
                        />
                    )}
                </Field>
                <Field label="LinkedIn URL">
                    {(props) => (
                        <input
                            {...props}
                            name="linkedin_url"
                            className="input"
                            type="url"
                            value={form.linkedin_url}
                            onChange={(e) => set("linkedin_url", e.target.value)}
                            maxLength={300}
                            placeholder="https://www.linkedin.com/in/…"
                        />
                    )}
                </Field>
            </FieldRow>

            <Field label="Short bio">
                {(props) => (
                    <textarea
                        {...props}
                        name="summary"
                        className="textarea"
                        rows={4}
                        value={form.summary}
                        onChange={(e) => set("summary", e.target.value)}
                        maxLength={2000}
                    />
                )}
            </Field>

            {children}
        </form>
    );
}
