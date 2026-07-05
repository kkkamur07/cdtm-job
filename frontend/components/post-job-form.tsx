"use client";

import { useActionState, useMemo, useState } from "react";

import { postJobAction, type PostJobActionState } from "@/app/post-job/actions";
import { CompanyAvatar } from "@/components/ui/company-avatar";
import {
  FormCheckboxField,
  FormField,
  FormSelect,
  FormTextArea,
  FormTextInput,
} from "@/components/ui/form-field";
import { FormSection, SegmentedControl } from "@/components/ui/form-section";
import type { CompanyPublic } from "@/lib/api/generated";
import { slugify } from "@/lib/slug";

const employmentTypes = [
  ["full_time", "Full-time"],
  ["part_time", "Part-time"],
  ["contract", "Contract"],
  ["internship", "Internship"],
  ["temporary", "Temporary"],
  ["working_student", "Working student"],
  ["freelance", "Freelance"],
] as const;

const workArrangements = [
  ["onsite", "On-site"],
  ["remote", "Remote"],
  ["hybrid", "Hybrid"],
] as const;

const experienceLevels = [
  ["intern", "Intern"],
  ["entry", "Entry"],
  ["mid", "Mid"],
  ["senior", "Senior"],
  ["lead", "Lead"],
] as const;

type Props = { companies: CompanyPublic[] };

export function PostJobForm({ companies }: Props) {
  const [source, setSource] = useState<"existing" | "new">(
    companies.length > 0 ? "existing" : "new",
  );
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [newCompanyName, setNewCompanyName] = useState("");
  const [slugOverride, setSlugOverride] = useState("");

  const [state, formAction, pending] = useActionState<PostJobActionState, FormData>(
    postJobAction,
    null,
  );

  const selectedCompany = useMemo(
    () => companies.find((c) => c.id === selectedCompanyId),
    [companies, selectedCompanyId],
  );

  const suggestedSlug = useMemo(() => {
    const raw = slugOverride.trim() || newCompanyName.trim();
    return raw ? slugify(raw) : "";
  }, [newCompanyName, slugOverride]);

  return (
    <form action={formAction} className="space-y-6">
      <input type="hidden" name="company_source" value={source} />

      {state?.error && (
        <div
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          {state.error}
        </div>
      )}

      <FormSection
        step={1}
        title="Company"
        description="Choose an organization already on the board, or add a new one in this step."
      >
        <SegmentedControl
          name="Company source"
          value={source}
          onChange={setSource}
          options={[
            { value: "existing", label: "Existing", disabled: companies.length === 0 },
            { value: "new", label: "New company" },
          ]}
        />

        {companies.length === 0 && (
          <p className="text-sm text-zinc-500">
            No companies on the board yet. You&apos;ll register one below.
          </p>
        )}

        {source === "existing" && (
          <div className="space-y-4">
            <FormField
              id="company_id"
              label="Organization"
              hint="The job will appear under this company's profile."
            >
              <FormSelect
                id="company_id"
                name="company_id"
                required={source === "existing"}
                disabled={source !== "existing"}
                value={selectedCompanyId}
                onChange={(e) => setSelectedCompanyId(e.target.value)}
              >
                <option value="">Select a company…</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </FormSelect>
            </FormField>

            {selectedCompany && (
              <div className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50/50 px-4 py-3">
                <CompanyAvatar
                  name={selectedCompany.name}
                  logoUrl={selectedCompany.logo_url}
                  className="h-11 w-11"
                />
                <div className="min-w-0">
                  <p className="text-ui-title truncate">{selectedCompany.name}</p>
                  <p className="mt-0.5 line-clamp-2 text-sm text-zinc-500">
                    {selectedCompany.short_description ||
                      [selectedCompany.industry, selectedCompany.hq_city]
                        .filter(Boolean)
                        .join(" · ") ||
                      "No description yet"}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {source === "new" && (
          <div className="space-y-5">
            <FormField id="new_company_name" label="Company name">
              <FormTextInput
                id="new_company_name"
                name="new_company_name"
                autoComplete="organization"
                required={source === "new"}
                disabled={source !== "new"}
                value={newCompanyName}
                onChange={(e) => setNewCompanyName(e.target.value)}
                placeholder="e.g. Alpine Robotics GmbH"
              />
            </FormField>

            <FormField
              id="new_company_slug"
              label="Public URL slug"
              optional
              hint={
                suggestedSlug
                  ? `Will publish as /companies/${suggestedSlug}.`
                  : "Leave empty to derive from the company name."
              }
            >
              <FormTextInput
                id="new_company_slug"
                name="new_company_slug"
                disabled={source !== "new"}
                value={slugOverride}
                onChange={(e) => setSlugOverride(e.target.value)}
                placeholder={suggestedSlug || "alpine-robotics"}
                className="font-mono text-[0.8125rem]"
              />
            </FormField>

            <div className="rounded-lg border border-zinc-200 border-dashed p-4">
              <p className="text-section-label mb-4">Optional profile details</p>
              <div className="space-y-4">
                <FormField id="new_company_short_description" label="Short description" optional>
                  <FormTextArea
                    id="new_company_short_description"
                    name="new_company_short_description"
                    rows={2}
                    disabled={source !== "new"}
                    placeholder="One line on what the company does."
                  />
                </FormField>

                <FormField id="new_company_website" label="Website" optional>
                  <FormTextInput
                    id="new_company_website"
                    name="new_company_website"
                    type="url"
                    disabled={source !== "new"}
                    placeholder="https://example.com"
                  />
                </FormField>

                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField id="new_company_industry" label="Industry" optional>
                    <FormTextInput
                      id="new_company_industry"
                      name="new_company_industry"
                      disabled={source !== "new"}
                      placeholder="e.g. Climate tech"
                    />
                  </FormField>
                  <FormField id="new_company_hq_city" label="HQ city" optional>
                    <FormTextInput
                      id="new_company_hq_city"
                      name="new_company_hq_city"
                      disabled={source !== "new"}
                      placeholder="e.g. Munich"
                    />
                  </FormField>
                </div>

                <FormField id="new_company_size_band" label="Company size" optional>
                  <FormSelect
                    id="new_company_size_band"
                    name="new_company_size_band"
                    disabled={source !== "new"}
                    defaultValue=""
                  >
                    <option value="">Select size…</option>
                    <option value="startup">Startup</option>
                    <option value="smb">SMB</option>
                    <option value="mid">Mid-market</option>
                    <option value="enterprise">Enterprise</option>
                  </FormSelect>
                </FormField>

                <FormCheckboxField
                  id="new_company_is_cdtm_startup"
                  name="new_company_is_cdtm_startup"
                  label="CDTM-affiliated startup"
                  hint="Show a badge for ventures connected to the CDTM ecosystem."
                  disabled={source !== "new"}
                />
              </div>
            </div>
          </div>
        )}
      </FormSection>

      <FormSection
        step={2}
        title="Role"
        description="What you're hiring for. This is what candidates see on the jobs board."
      >
        <FormField id="title" label="Job title">
          <FormTextInput
            id="title"
            name="title"
            required
            placeholder="e.g. Product Manager, Growth"
          />
        </FormField>

        <FormField
          id="summary"
          label="Short summary"
          optional
          hint="Shown in search results. Keep it to one compelling sentence."
        >
          <FormTextInput
            id="summary"
            name="summary"
            maxLength={1024}
            placeholder="What makes this role exciting?"
          />
        </FormField>

        <FormField
          id="description"
          label="Full description"
          hint="Responsibilities, requirements, and what success looks like."
        >
          <FormTextArea
            id="description"
            name="description"
            required
            rows={10}
            placeholder="Describe the role, team, and who would thrive here…"
            className="min-h-[12rem]"
          />
        </FormField>

        <div className="grid gap-4 sm:grid-cols-3">
          <FormField id="employment_type" label="Employment type">
            <FormSelect id="employment_type" name="employment_type" required defaultValue="full_time">
              {employmentTypes.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </FormSelect>
          </FormField>
          <FormField id="work_arrangement" label="Work arrangement">
            <FormSelect id="work_arrangement" name="work_arrangement" required defaultValue="hybrid">
              {workArrangements.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </FormSelect>
          </FormField>
          <FormField id="experience_level" label="Experience level">
            <FormSelect id="experience_level" name="experience_level" required defaultValue="mid">
              {experienceLevels.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </FormSelect>
          </FormField>
        </div>

        <FormField
          id="location_display"
          label="Location"
          optional
          hint='How it appears on the listing, e.g. "Munich · hybrid" or "Remote (EU)".'
        >
          <FormTextInput
            id="location_display"
            name="location_display"
            placeholder="Munich, Germany"
          />
        </FormField>
      </FormSection>

      <FormSection
        step={3}
        title="How to apply"
        description="Give candidates a clear next step. Add a URL, an email, or both."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id="application_url" label="Application URL" optional>
            <FormTextInput
              id="application_url"
              name="application_url"
              type="url"
              placeholder="https://careers.example.com/apply"
            />
          </FormField>
          <FormField id="application_email" label="Application email" optional>
            <FormTextInput
              id="application_email"
              name="application_email"
              type="email"
              placeholder="careers@example.com"
            />
          </FormField>
        </div>
      </FormSection>

      <div className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white px-5 py-5 shadow-sm sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p className="text-sm text-zinc-500">
          Your listing goes live on the jobs board as soon as you publish.
        </p>
        <button
          type="submit"
          disabled={pending}
          className="inline-flex shrink-0 items-center justify-center rounded-lg bg-cdtm px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-cdtm-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2 disabled:opacity-60"
        >
          {pending ? "Publishing…" : "Publish job"}
        </button>
      </div>
    </form>
  );
}
