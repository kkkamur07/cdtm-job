"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { useCreateMyProfile, useFacets, useMe } from "@/api/hooks/me";
import type { SelfProfileCreate } from "@/api/types";
import Field, { FieldRow } from "@/components/Field";
import { FormError } from "@/components/states";
import { useSession } from "@/auth/AuthProvider";
import { readyToSubmit } from "@/lib/forms";

/**
 * The form a signed-in account fills in when no roster row matched its e-mail.
 *
 * It is a claim of yourself, so the two facts that identify the account, the
 * e-mail and the Google avatar, are shown but never editable: they come from
 * the token, not the form. Everything a LinkedIn scrape would add is left for a
 * later profile edit rather than invented here; only a name, a class and a
 * study are required.
 */
type FormState = {
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

export default function OnboardingForm() {
    const router = useRouter();
    const { email } = useSession();
    const me = useMe();
    const facets = useFacets();
    const create = useCreateMyProfile();

    const account = me.data?.account;
    const alreadyLinked = me.data?.member_id != null;

    const [form, setForm] = useState<FormState>({
        name: "",
        class_id: "",
        major: "",
        headline: "",
        current_company: "",
        current_title: "",
        location: "",
        linkedin_url: "",
        summary: "",
    });
    // Name defaults to the Google display name the first time it is known, and only then, so
    // the field is never yanked out from under someone who has started editing it.
    const [namePrefilled, setNamePrefilled] = useState(false);
    if (!namePrefilled && account?.full_name && !form.name) {
        setForm((prev) => ({ ...prev, name: account.full_name ?? "" }));
        setNamePrefilled(true);
    }

    const set = (key: keyof FormState, value: string) =>
        setForm((prev) => ({ ...prev, [key]: value }));

    // Newest class first: a member joining now is far likelier to be in a recent batch.
    const classes = useMemo(
        () => [...(facets.data?.classes ?? [])].sort((a, b) => b.year - a.year),
        [facets.data],
    );
    const majors = facets.data?.majors ?? [];

    if (alreadyLinked) {
        return (
            <div className="card p-6 text-[13.5px] leading-relaxed">
                <h1 className="mb-2 text-lg font-semibold">You already have a profile</h1>
                <p className="mb-4 text-muted">Your account is linked to a member already.</p>
                <button className="btn btn-blue" onClick={() => router.push("/me")}>
                    Go to my profile
                </button>
            </div>
        );
    }

    const submit = (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (
            !readyToSubmit(event.currentTarget, [
                { name: "name", value: form.name, label: "Name" },
                { name: "major", value: form.major, label: "Study" },
            ])
        ) {
            return;
        }
        if (!form.class_id) return;

        const body: SelfProfileCreate = {
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
        create.mutate(body, {
            onSuccess: (profile) => router.push(`/members/${profile.slug}`),
        });
    };

    return (
        <div className="w-full max-w-[34rem]">
            <div className="mb-6 flex items-center gap-3">
                {account?.avatar_url ? (
                    // Plain <img>: the Google avatar is a remote URL, and the CSP allows
                    // googleusercontent as an image source. next/image is not needed here.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                        src={account.avatar_url}
                        alt=""
                        width={48}
                        height={48}
                        className="h-12 w-12 rounded-full object-cover"
                    />
                ) : null}
                <div>
                    <h1 className="text-lg font-semibold">Create your profile</h1>
                    <p className="text-[13px] text-muted">
                        Signed in as <b>{email ?? account?.email}</b>. This is your entry in the
                        CDTM directory.
                    </p>
                </div>
            </div>

            <form onSubmit={submit} noValidate className="card flex flex-col gap-4 p-5">
                <FormError error={create.error} />

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
                                    {facets.isLoading ? "Loading…" : "Select your class"}
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
                                list="majors"
                                maxLength={160}
                            />
                        )}
                    </Field>
                </FieldRow>
                <datalist id="majors">
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

                <div className="mt-1 flex items-center gap-3">
                    <button type="submit" className="btn btn-blue" disabled={create.isPending}>
                        {create.isPending ? "Creating…" : "Create profile"}
                    </button>
                    <span className="text-[12px] text-muted">
                        Your photo and e-mail come from your Google account.
                    </span>
                </div>
            </form>
        </div>
    );
}
