"use client";

import { useMemo, useState } from "react";

import { useFacets, useMyMember, useUpdateMyProfile } from "@/api/hooks/me";
import { FormError } from "@/components/states";
import { LoadingBlock } from "@/components/placeholders";
import { readyToSubmit } from "@/lib/forms";
import {
    profileFromMember,
    ProfileFormBody,
    toProfilePayload,
    type ProfileFormState,
} from "./profileForm";

/**
 * Editing the profile you already have. The same fields as onboarding, so an
 * imported member who just signed in and a self-created one change the same
 * things. Only the profile columns are written here: the "Your entry" tab still
 * owns the networking extras, and a scrape's positions are never touched.
 */
export default function EditProfileForm() {
    const member = useMyMember();
    const facets = useFacets();
    const update = useUpdateMyProfile();

    // Start from the current profile, once. `key` on the mount (below) reloads it if the
    // member changes underneath; within an edit, the form is the source of truth.
    const [form, setForm] = useState<ProfileFormState | null>(null);
    if (form === null && member.data) setForm(profileFromMember(member.data));

    const set = (key: keyof ProfileFormState, value: string) =>
        setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

    const classes = useMemo(
        () => [...(facets.data?.classes ?? [])].sort((a, b) => b.year - a.year),
        [facets.data],
    );
    const majors = facets.data?.majors ?? [];

    if (member.isLoading || form === null) {
        return <LoadingBlock label="Loading your profile" rows={4} />;
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
        update.mutate(toProfilePayload(form));
    };

    return (
        <ProfileFormBody
            form={form}
            set={set}
            classes={classes}
            majors={majors}
            classesLoading={facets.isLoading}
            onSubmit={submit}
        >
            <FormError error={update.error} />
            <div className="mt-1 flex items-center gap-3">
                <button type="submit" className="btn btn-blue" disabled={update.isPending}>
                    {update.isPending ? "Saving…" : "Save profile"}
                </button>
                {update.isSuccess && !update.isPending && (
                    <span className="text-[12.5px] text-muted" role="status">
                        Saved.
                    </span>
                )}
                <span className="ml-auto text-[12px] text-muted">
                    Your photo and e-mail come from your Google account.
                </span>
            </div>
        </ProfileFormBody>
    );
}
