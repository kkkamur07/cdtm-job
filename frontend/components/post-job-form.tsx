"use client";

import { useActionState, useState } from "react";

import { postJobAction, type PostJobActionState } from "@/app/post-job/actions";
import type { CompanyPublic } from "@/lib/api/generated";

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

const labelClass =
  "mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300";
const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm focus:border-cdtm focus:outline-none focus:ring-1 focus:ring-cdtm disabled:cursor-not-allowed disabled:bg-zinc-100 disabled:opacity-70 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50 dark:disabled:bg-zinc-900";

type Props = { companies: CompanyPublic[] };

export function PostJobForm({ companies }: Props) {
  const [source, setSource] = useState<"existing" | "new">(
    companies.length > 0 ? "existing" : "new",
  );
  const [state, formAction, pending] = useActionState<PostJobActionState, FormData>(
    postJobAction,
    null,
  );

  return (
    <form action={formAction} className="max-w-xl space-y-6">
      <input type="hidden" name="company_source" value={source} />

      {state?.error && (
        <p
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200"
          role="alert"
        >
          {state.error}
        </p>
      )}

      <fieldset className="space-y-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <legend className="px-1 text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          Company
        </legend>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Use an organization already on the board, or register a new one in the same step.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSource("existing")}
            disabled={companies.length === 0}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              source === "existing"
                ? "bg-cdtm text-white"
                : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            Existing company
          </button>
          <button
            type="button"
            onClick={() => setSource("new")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              source === "new"
                ? "bg-cdtm text-white"
                : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            }`}
          >
            New company
          </button>
        </div>
        {companies.length === 0 && (
          <p className="text-xs text-zinc-500">No companies yet — use “New company” below.</p>
        )}

        {source === "existing" && (
          <div>
            <label htmlFor="company_id" className={labelClass}>
              Select company
            </label>
            <select
              id="company_id"
              name="company_id"
              required={source === "existing"}
              disabled={source !== "existing"}
              className={inputClass}
            >
              <option value="">Choose…</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {source === "new" && (
          <div className="space-y-4 border-t border-zinc-100 pt-4 dark:border-zinc-800">
            <div>
              <label htmlFor="new_company_name" className={labelClass}>
                Company name
              </label>
              <input
                id="new_company_name"
                name="new_company_name"
                autoComplete="organization"
                required={source === "new"}
                disabled={source !== "new"}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="new_company_slug" className={labelClass}>
                URL slug (optional)
              </label>
              <input
                id="new_company_slug"
                name="new_company_slug"
                disabled={source !== "new"}
                className={inputClass}
                placeholder="Derived from name if empty"
              />
            </div>
            <div>
              <label htmlFor="new_company_short_description" className={labelClass}>
                Short description (optional)
              </label>
              <textarea
                id="new_company_short_description"
                name="new_company_short_description"
                rows={2}
                disabled={source !== "new"}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="new_company_website" className={labelClass}>
                Website (optional)
              </label>
              <input
                id="new_company_website"
                name="new_company_website"
                type="url"
                disabled={source !== "new"}
                className={inputClass}
                placeholder="https://"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="new_company_industry" className={labelClass}>
                  Industry (optional)
                </label>
                <input
                  id="new_company_industry"
                  name="new_company_industry"
                  disabled={source !== "new"}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="new_company_hq_city" className={labelClass}>
                  HQ city (optional)
                </label>
                <input
                  id="new_company_hq_city"
                  name="new_company_hq_city"
                  disabled={source !== "new"}
                  className={inputClass}
                />
              </div>
            </div>
            <div>
              <label htmlFor="new_company_size_band" className={labelClass}>
                Company size (optional)
              </label>
              <select
                id="new_company_size_band"
                name="new_company_size_band"
                disabled={source !== "new"}
                className={inputClass}
              >
                <option value="">—</option>
                <option value="startup">Startup</option>
                <option value="smb">SMB</option>
                <option value="mid">Mid</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <input
                id="new_company_is_cdtm_startup"
                name="new_company_is_cdtm_startup"
                type="checkbox"
                disabled={source !== "new"}
                className="rounded border-zinc-300 disabled:opacity-50"
              />
              <label
                htmlFor="new_company_is_cdtm_startup"
                className="text-sm text-zinc-700 dark:text-zinc-300"
              >
                CDTM-affiliated startup
              </label>
            </div>
          </div>
        )}
      </fieldset>

      <div className="space-y-5">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Job details</h2>

        <div>
          <label htmlFor="title" className={labelClass}>
            Title
          </label>
          <input id="title" name="title" required className={inputClass} />
        </div>

        <div>
          <label htmlFor="summary" className={labelClass}>
            Short summary (optional)
          </label>
          <input id="summary" name="summary" className={inputClass} maxLength={1024} />
        </div>

        <div>
          <label htmlFor="description" className={labelClass}>
            Description
          </label>
          <textarea id="description" name="description" required rows={8} className={inputClass} />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="employment_type" className={labelClass}>
              Employment
            </label>
            <select id="employment_type" name="employment_type" required className={inputClass}>
              {employmentTypes.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="work_arrangement" className={labelClass}>
              Work arrangement
            </label>
            <select id="work_arrangement" name="work_arrangement" required className={inputClass}>
              {workArrangements.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="experience_level" className={labelClass}>
              Experience
            </label>
            <select id="experience_level" name="experience_level" required className={inputClass}>
              {experienceLevels.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="location_display" className={labelClass}>
            Location (optional)
          </label>
          <input id="location_display" name="location_display" className={inputClass} />
        </div>

        <div>
          <label htmlFor="application_url" className={labelClass}>
            Application URL (optional)
          </label>
          <input
            id="application_url"
            name="application_url"
            type="url"
            className={inputClass}
            placeholder="https://"
          />
        </div>

        <div>
          <label htmlFor="application_email" className={labelClass}>
            Application email (optional)
          </label>
          <input id="application_email" name="application_email" type="email" className={inputClass} />
        </div>
      </div>

      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-cdtm px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-cdtm-hover disabled:opacity-60"
      >
        {pending ? "Publishing…" : "Publish job"}
      </button>
    </form>
  );
}
