"use client";

import { useState } from "react";

import type { HousingCreate, HousingKind, HousingListing, HousingStatus } from "@/api/types";
import Field, { FieldRow } from "@/components/Field";
import { FormError } from "@/components/states";
import ImageUpload from "@/components/ImageUpload";
import { joinList, parseList } from "@/lib/format";
import { readyToSubmit } from "@/lib/forms";

type FormState = {
    kind: HousingKind;
    title: string;
    city: string;
    area: string;
    price_eur: string;
    rooms: string;
    available_from: string;
    available_until: string;
    description: string;
    photo_urls: string;
    status: HousingStatus;
};

function seed(listing?: HousingListing): FormState {
    return {
        kind: listing?.kind ?? "offer",
        title: listing?.title ?? "",
        city: listing?.city ?? "",
        area: listing?.area ?? "",
        price_eur: listing?.price_eur != null ? String(listing.price_eur) : "",
        rooms: listing?.rooms ?? "",
        available_from: listing?.available_from ?? "",
        available_until: listing?.available_until ?? "",
        description: listing?.description ?? "",
        photo_urls: joinList(listing?.photo_urls),
        status: listing?.status ?? "open",
    };
}

/**
 * One form for posting and for editing. `kind` is fixed once a listing exists
 * (the API has no way to flip an offer into a search), so it is only editable
 * on the way in.
 */
export default function HousingForm({
    listing,
    submitLabel,
    pending,
    error,
    onSubmit,
    footer,
}: {
    listing?: HousingListing;
    submitLabel: string;
    pending: boolean;
    error: unknown;
    onSubmit: (body: HousingCreate & { status?: HousingStatus }) => void;
    footer?: React.ReactNode;
}) {
    const [form, setForm] = useState<FormState>(() => seed(listing));
    const set = (key: keyof FormState, value: string) =>
        setForm((prev) => ({ ...prev, [key]: value }));

    const submit = (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (
            !readyToSubmit(event.currentTarget, [
                { name: "title", value: form.title, label: "Title" },
                { name: "city", value: form.city, label: "City" },
            ])
        ) {
            return;
        }

        onSubmit({
            kind: form.kind,
            title: form.title.trim(),
            city: form.city.trim(),
            area: form.area.trim() || null,
            price_eur: form.price_eur ? Number(form.price_eur) : null,
            rooms: form.rooms.trim() || null,
            available_from: form.available_from || null,
            available_until: form.available_until || null,
            description: form.description.trim() || null,
            photo_urls: parseList(form.photo_urls),
            status: form.status,
        });
    };

    return (
        <form className="grid gap-4" onSubmit={submit}>
            {!listing && (
                <Field label="What is this">
                    {(props) => (
                        <select
                            {...props}
                            className="select"
                            value={form.kind}
                            onChange={(event) => set("kind", event.target.value)}
                        >
                            <option value="offer">I am offering a place</option>
                            <option value="looking">I am looking for a place</option>
                        </select>
                    )}
                </Field>
            )}

            <Field label="Title" required>
                {(props) => (
                    <input
                        {...props}
                        name="title"
                        className="input"
                        required
                        value={form.title}
                        onChange={(event) => set("title", event.target.value)}
                        placeholder="Bright room in Maxvorstadt, sublet until March"
                    />
                )}
            </Field>

            <FieldRow>
                <Field label="City" required>
                    {(props) => (
                        <input
                            {...props}
                            name="city"
                            className="input"
                            required
                            value={form.city}
                            onChange={(event) => set("city", event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Area">
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={form.area}
                            onChange={(event) => set("area", event.target.value)}
                            placeholder="Maxvorstadt"
                        />
                    )}
                </Field>
            </FieldRow>

            <FieldRow>
                <Field label="Rent per month" hint="Euros, numbers only.">
                    {(props) => (
                        <input
                            {...props}
                            type="number"
                            min={0}
                            className="input"
                            value={form.price_eur}
                            onChange={(event) => set("price_eur", event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Rooms">
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={form.rooms}
                            onChange={(event) => set("rooms", event.target.value)}
                            placeholder="1.5"
                        />
                    )}
                </Field>
            </FieldRow>

            <FieldRow>
                <Field label="Available from">
                    {(props) => (
                        <input
                            {...props}
                            type="date"
                            className="input"
                            value={form.available_from}
                            onChange={(event) => set("available_from", event.target.value)}
                        />
                    )}
                </Field>
                <Field label="Available until">
                    {(props) => (
                        <input
                            {...props}
                            type="date"
                            className="input"
                            value={form.available_until}
                            onChange={(event) => set("available_until", event.target.value)}
                        />
                    )}
                </Field>
            </FieldRow>

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

            <ImageUpload
                kind="housing-photo"
                label="Photos"
                hint="JPEG, PNG or WebP, up to 5 MB each. The first one is the cover."
                multiple
                urls={parseList(form.photo_urls)}
                onChange={(urls) => set("photo_urls", urls.join(", "))}
            />

            {listing && (
                <Field label="Status" hint="Close a listing once it is taken.">
                    {(props) => (
                        <select
                            {...props}
                            className="select"
                            value={form.status}
                            onChange={(event) => set("status", event.target.value)}
                        >
                            <option value="open">Open</option>
                            <option value="closed">Closed</option>
                        </select>
                    )}
                </Field>
            )}

            <FormError error={error} />

            <div className="flex gap-2">
                <button type="submit" className="btn btn-primary" disabled={pending}>
                    {pending ? "Saving…" : submitLabel}
                </button>
                {footer}
            </div>
        </form>
    );
}
