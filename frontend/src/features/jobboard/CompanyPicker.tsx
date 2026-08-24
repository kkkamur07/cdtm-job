"use client";

import { useState } from "react";

import { useCompanies, useCreateCompany } from "@/api/hooks/jobboard";
import Field, { FieldRow } from "@/components/Field";
import { FormError } from "@/components/states";
import { slugify } from "@/lib/format";

/**
 * Pick the company the role is at, or add it if it is not there yet.
 *
 * Creating a company is folded into this form rather than being a separate
 * page: the only reason anyone creates one is that they are halfway through
 * posting a job, and sending them away loses the draft.
 */
export default function CompanyPicker({
    value,
    onChange,
}: {
    value: string;
    onChange: (companyId: string) => void;
}) {
    const companies = useCompanies();
    const create = useCreateCompany();
    const [adding, setAdding] = useState(false);
    const [name, setName] = useState("");
    const [website, setWebsite] = useState("");
    const [logo, setLogo] = useState("");

    const options = [...(companies.data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name));

    const submitNew = () => {
        create.mutate(
            {
                name: name.trim(),
                slug: slugify(name),
                website_url: website.trim() || null,
                logo_url: logo.trim() || null,
                is_cdtm_startup: false,
            },
            {
                onSuccess: (company) => {
                    onChange(company.id);
                    setAdding(false);
                    setName("");
                    setWebsite("");
                    setLogo("");
                },
            },
        );
    };

    if (adding) {
        // Not a nested <form>: this sits inside the job form, and nesting forms
        // is invalid HTML that browsers resolve by dropping the inner one.
        return (
            <div className="grid gap-3 rounded-2xl border border-line bg-cream p-3.5">
                <p className="text-[13px] font-semibold">Add a company</p>
                <Field label="Company name" required>
                    {(props) => (
                        <input
                            {...props}
                            className="input"
                            value={name}
                            onChange={(event) => setName(event.target.value)}
                        />
                    )}
                </Field>
                <FieldRow>
                    <Field label="Website">
                        {(props) => (
                            <input
                                {...props}
                                type="url"
                                className="input"
                                value={website}
                                onChange={(event) => setWebsite(event.target.value)}
                                placeholder="https://"
                            />
                        )}
                    </Field>
                    <Field label="Logo URL">
                        {(props) => (
                            <input
                                {...props}
                                type="url"
                                className="input"
                                value={logo}
                                onChange={(event) => setLogo(event.target.value)}
                                placeholder="https://"
                            />
                        )}
                    </Field>
                </FieldRow>
                <FormError error={create.error} />
                <div className="flex gap-2">
                    <button
                        type="button"
                        className="btn btn-sm btn-blue"
                        disabled={create.isPending || !name.trim()}
                        onClick={submitNew}
                    >
                        {create.isPending ? "Adding…" : "Add company"}
                    </button>
                    <button type="button" className="btn btn-sm btn-ghost" onClick={() => setAdding(false)}>
                        Cancel
                    </button>
                </div>
            </div>
        );
    }

    return (
        <Field label="Company" required hint="Not listed? Add it without leaving this form.">
            {(props) => (
                <div className="flex flex-wrap gap-2">
                    <select
                        {...props}
                        name="company_id"
                        className="select min-w-[12rem] flex-1"
                        required
                        value={value}
                        onChange={(event) => onChange(event.target.value)}
                    >
                        <option value="">
                            {companies.isPending ? "Loading companies…" : "Select a company"}
                        </option>
                        {options.map((company) => (
                            <option key={company.id} value={company.id}>
                                {company.name}
                            </option>
                        ))}
                    </select>
                    <button type="button" className="btn" onClick={() => setAdding(true)}>
                        Add company
                    </button>
                </div>
            )}
        </Field>
    );
}
