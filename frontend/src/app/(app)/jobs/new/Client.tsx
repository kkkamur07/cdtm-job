"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCreateJob } from "@/api/hooks/jobboard";
import type { EmploymentType, ExperienceLevel, WorkArrangement } from "@/api/types";
import Field, { FieldRow } from "@/components/Field";
import ImageUpload from "@/components/ImageUpload";
import Panel from "@/components/Panel";
import { FormError } from "@/components/states";
import CompanyPicker from "@/features/jobboard/CompanyPicker";
import { humanise, parseList, slugify } from "@/lib/format";
import { readyToSubmit } from "@/lib/forms";

const EMPLOYMENT: EmploymentType[] = [
    "full_time",
    "part_time",
    "internship",
    "working_student",
    "contract",
    "freelance",
    "temporary",
];
const LEVELS: ExperienceLevel[] = ["intern", "entry", "mid", "senior", "lead"];
const ARRANGEMENTS: WorkArrangement[] = ["onsite", "hybrid", "remote"];

export default function PostJobForm() {
    const router = useRouter();
    const create = useCreateJob();
    const [companyId, setCompanyId] = useState("");
    const [form, setForm] = useState({
        title: "",
        summary: "",
        description: "",
        employment_type: "full_time" as EmploymentType,
        experience_level: "mid" as ExperienceLevel,
        work_arrangement: "hybrid" as WorkArrangement,
        location_display: "",
        application_url: "",
        application_email: "",
        must_have_skills: "",
        salary_min: "",
        salary_max: "",
        image_url: "",
    });

    const set = (key: keyof typeof form, value: string) =>
        setForm((prev) => ({ ...prev, [key]: value }));

    const submit = (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (
            !readyToSubmit(event.currentTarget, [
                { name: "title", value: form.title, label: "Title" },
                { name: "description", value: form.description, label: "Description" },
            ])
        ) {
            return;
        }

        create.mutate(
            {
                company_id: companyId,
                title: form.title.trim(),
                slug: slugify(form.title),
                summary: form.summary.trim() || null,
                description: form.description.trim(),
                employment_type: form.employment_type,
                experience_level: form.experience_level,
                work_arrangement: form.work_arrangement,
                location_display: form.location_display.trim() || null,
                application_url: form.application_url.trim() || null,
                application_email: form.application_email.trim() || null,
                must_have_skills: parseList(form.must_have_skills),
                image_url: form.image_url || null,
                salary_min: form.salary_min ? Number(form.salary_min) : null,
                salary_max: form.salary_max ? Number(form.salary_max) : null,
                salary_currency: form.salary_min || form.salary_max ? "EUR" : null,
                salary_period: form.salary_min || form.salary_max ? "yearly" : null,
                compensation_disclosure: form.salary_min || form.salary_max ? "public" : "undisclosed",
                // No `posted_by_member_id`: the API stamps the poster from the
                // authenticated caller, so sending one is at best redundant and
                // at worst a claim the client is not entitled to make.
                status: "published",
            },
            { onSuccess: (job) => router.push(`/jobs/${job.slug ?? job.id}`) },
        );
    };

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <Link href="/jobs" className="w-fit text-[12.5px] font-medium text-blue hover:underline">
                Back to jobs
            </Link>

            <Panel title="Post a job">
                <form className="grid gap-4" onSubmit={submit}>
                    <CompanyPicker value={companyId} onChange={setCompanyId} />

                    <Field label="Title" required>
                        {(props) => (
                            <input
                                {...props}
                                name="title"
                                className="input"
                                required
                                value={form.title}
                                onChange={(event) => set("title", event.target.value)}
                            />
                        )}
                    </Field>

                    <Field label="One line summary">
                        {(props) => (
                            <input
                                {...props}
                                className="input"
                                value={form.summary}
                                onChange={(event) => set("summary", event.target.value)}
                            />
                        )}
                    </Field>

                    <Field label="Description" required hint="What the role is, who it suits, how you work.">
                        {(props) => (
                            <textarea
                                {...props}
                                name="description"
                                className="textarea min-h-[180px]"
                                required
                                value={form.description}
                                onChange={(event) => set("description", event.target.value)}
                            />
                        )}
                    </Field>

                    <FieldRow>
                        <Select
                            label="Employment"
                            value={form.employment_type}
                            options={EMPLOYMENT}
                            onChange={(value) => set("employment_type", value)}
                        />
                        <Select
                            label="Experience"
                            value={form.experience_level}
                            options={LEVELS}
                            onChange={(value) => set("experience_level", value)}
                        />
                    </FieldRow>

                    <FieldRow>
                        <Select
                            label="Arrangement"
                            value={form.work_arrangement}
                            options={ARRANGEMENTS}
                            onChange={(value) => set("work_arrangement", value)}
                        />
                        <Field label="Location">
                            {(props) => (
                                <input
                                    {...props}
                                    className="input"
                                    value={form.location_display}
                                    onChange={(event) => set("location_display", event.target.value)}
                                    placeholder="Munich, Germany"
                                />
                            )}
                        </Field>
                    </FieldRow>

                    <FieldRow>
                        <Field label="Salary from" hint="Euros per year. Leave both empty to not disclose.">
                            {(props) => (
                                <input
                                    {...props}
                                    type="number"
                                    min={0}
                                    className="input"
                                    value={form.salary_min}
                                    onChange={(event) => set("salary_min", event.target.value)}
                                />
                            )}
                        </Field>
                        <Field label="Salary to">
                            {(props) => (
                                <input
                                    {...props}
                                    type="number"
                                    min={0}
                                    className="input"
                                    value={form.salary_max}
                                    onChange={(event) => set("salary_max", event.target.value)}
                                />
                            )}
                        </Field>
                    </FieldRow>

                    <ImageUpload
                        kind="job-image"
                        label="Cover image"
                        hint="Optional. JPEG, PNG or WebP up to 5 MB. Landscape works best."
                        urls={form.image_url ? [form.image_url] : []}
                        onChange={(urls) => set("image_url", urls[0] ?? "")}
                    />

                    <Field label="Must-have skills" hint="Comma separated.">
                        {(props) => (
                            <input
                                {...props}
                                className="input"
                                value={form.must_have_skills}
                                onChange={(event) => set("must_have_skills", event.target.value)}
                            />
                        )}
                    </Field>

                    <FieldRow>
                        <Field label="Application link">
                            {(props) => (
                                <input
                                    {...props}
                                    type="url"
                                    className="input"
                                    value={form.application_url}
                                    onChange={(event) => set("application_url", event.target.value)}
                                    placeholder="https://"
                                />
                            )}
                        </Field>
                        <Field label="Or application email">
                            {(props) => (
                                <input
                                    {...props}
                                    type="email"
                                    className="input"
                                    value={form.application_email}
                                    onChange={(event) => set("application_email", event.target.value)}
                                />
                            )}
                        </Field>
                    </FieldRow>

                    <FormError error={create.error} />

                    <div className="flex gap-2">
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={create.isPending}
                        >
                            {create.isPending ? "Publishing…" : "Publish role"}
                        </button>
                        <Link href="/jobs" className="btn btn-ghost">
                            Cancel
                        </Link>
                    </div>
                </form>
            </Panel>
        </div>
    );
}

function Select<T extends string>({
    label,
    value,
    options,
    onChange,
}: {
    label: string;
    value: T;
    options: readonly T[];
    onChange: (value: T) => void;
}) {
    return (
        <Field label={label}>
            {(props) => (
                <select
                    {...props}
                    className="select capitalize"
                    value={value}
                    onChange={(event) => onChange(event.target.value as T)}
                >
                    {options.map((option) => (
                        <option key={option} value={option}>
                            {humanise(option)}
                        </option>
                    ))}
                </select>
            )}
        </Field>
    );
}
