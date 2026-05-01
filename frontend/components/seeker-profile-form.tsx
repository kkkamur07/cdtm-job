"use client";

import { useActionState } from "react";

import { createSeekerAction, type SeekerActionState } from "@/app/seekers/actions";

const labelClass =
  "mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300";
const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm focus:border-cdtm focus:outline-none focus:ring-1 focus:ring-cdtm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50";

export function SeekerProfileForm() {
  const [state, formAction, pending] = useActionState<SeekerActionState, FormData>(
    createSeekerAction,
    null,
  );

  return (
    <form action={formAction} className="max-w-xl space-y-5">
      {state?.error && (
        <p
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200"
          role="alert"
        >
          {state.error}
        </p>
      )}

      <div>
        <label htmlFor="full_name" className={labelClass}>
          Full name
        </label>
        <input id="full_name" name="full_name" required className={inputClass} />
      </div>

      <div>
        <label htmlFor="email" className={labelClass}>
          Email (optional)
        </label>
        <input id="email" name="email" type="email" className={inputClass} />
      </div>

      <div>
        <label htmlFor="headline" className={labelClass}>
          Headline (optional)
        </label>
        <input id="headline" name="headline" className={inputClass} />
      </div>

      <div>
        <label htmlFor="bio" className={labelClass}>
          Bio (optional)
        </label>
        <textarea id="bio" name="bio" rows={5} className={inputClass} />
      </div>

      <div>
        <label htmlFor="skills" className={labelClass}>
          Skills (comma-separated)
        </label>
        <input id="skills" name="skills" className={inputClass} placeholder="Python, React, …" />
      </div>

      <div>
        <label htmlFor="languages" className={labelClass}>
          Languages (comma-separated, optional)
        </label>
        <input id="languages" name="languages" className={inputClass} placeholder="English, German" />
      </div>

      <div>
        <label htmlFor="years_of_experience" className={labelClass}>
          Years of experience (optional)
        </label>
        <input
          id="years_of_experience"
          name="years_of_experience"
          type="number"
          min={0}
          max={80}
          className={inputClass}
        />
      </div>

      <div className="flex items-center gap-2">
        <input id="open_to_remote" name="open_to_remote" type="checkbox" className="rounded border-zinc-300" />
        <label htmlFor="open_to_remote" className="text-sm text-zinc-700 dark:text-zinc-300">
          Open to remote
        </label>
      </div>

      <div>
        <label htmlFor="linkedin_url" className={labelClass}>
          LinkedIn URL (optional)
        </label>
        <input id="linkedin_url" name="linkedin_url" type="url" className={inputClass} />
      </div>

      <div>
        <label htmlFor="portfolio_url" className={labelClass}>
          Portfolio URL (optional)
        </label>
        <input id="portfolio_url" name="portfolio_url" type="url" className={inputClass} />
      </div>

      <div>
        <label htmlFor="github_url" className={labelClass}>
          GitHub URL (optional)
        </label>
        <input id="github_url" name="github_url" type="url" className={inputClass} />
      </div>

      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-cdtm px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-cdtm-hover disabled:opacity-60"
      >
        {pending ? "Saving…" : "Create profile"}
      </button>
    </form>
  );
}
