"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { useCreateMyProfile, useFacets, useMe } from "@/api/hooks/me";
import { FormError } from "@/components/states";
import { useSession } from "@/auth/AuthProvider";
import { readyToSubmit } from "@/lib/forms";
import {
    emptyProfileForm,
    ProfileFormBody,
    toProfilePayload,
    type ProfileFormState,
} from "@/features/community/me/profileForm";

/**
 * The form a signed-in account fills in when no roster row matched its e-mail.
 *
 * It is a claim of yourself, so the two facts that identify the account, the
 * e-mail and the Google avatar, are shown but never editable: they come from
 * the token, not the form. It shares its body with the edit form on your
 * account page, so creating and later editing a profile are the same fields.
 */
export default function OnboardingForm() {
    const router = useRouter();
    const { email } = useSession();
    const me = useMe();
    const facets = useFacets();
    const create = useCreateMyProfile();

    const account = me.data?.account;
    const alreadyLinked = me.data?.member_id != null;

    const [form, setForm] = useState<ProfileFormState>(emptyProfileForm);
    // Name defaults to the Google display name the first time it is known, and only then, so
    // the field is never yanked out from under someone who has started editing it.
    const [namePrefilled, setNamePrefilled] = useState(false);
    if (!namePrefilled && account?.full_name && !form.name) {
        setForm((prev) => ({ ...prev, name: account.full_name ?? "" }));
        setNamePrefilled(true);
    }

    const set = (key: keyof ProfileFormState, value: string) =>
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

        create.mutate(toProfilePayload(form), {
            onSuccess: (profile) => router.push(`/members/${profile.slug}`),
        });
    };

    return (
        <div className="w-full max-w-[34rem]">
            <div className="mb-6 flex items-center gap-3">
                {account?.avatar_url ? (
                    // Plain <img>: the Google avatar is a remote URL, and the CSP allows
                    // googleusercontent as an image source. next/image is not needed here.
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

            <ProfileFormBody
                form={form}
                set={set}
                classes={classes}
                majors={majors}
                classesLoading={facets.isLoading}
                onSubmit={submit}
            >
                <FormError error={create.error} />
                <div className="mt-1 flex items-center gap-3">
                    <button type="submit" className="btn btn-blue" disabled={create.isPending}>
                        {create.isPending ? "Creating…" : "Create profile"}
                    </button>
                    <span className="text-[12px] text-muted">
                        Your photo and e-mail come from your Google account.
                    </span>
                </div>
            </ProfileFormBody>
        </div>
    );
}
