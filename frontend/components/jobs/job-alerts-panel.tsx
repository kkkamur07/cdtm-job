"use client";

import { useEffect, useMemo, useState } from "react";

import { countMatchingJobs } from "@/lib/filter-jobs";
import {
  cadenceLabel,
  createJobAlert,
  defaultAlertLabel,
  describeAlertCriteria,
  EMPLOYMENT_TYPES,
  EXPERIENCE_LEVELS,
  loadJobAlerts,
  loadSubscriberPrefs,
  personalizedAlertLabel,
  removeJobAlert,
  WORK_ARRANGEMENTS,
  type AlertCadence,
  type JobAlertCriteria,
  type JobAlertRecord,
} from "@/lib/job-alerts";
import { formatLabel } from "@/lib/format-job";
import { toggleSetValue } from "@/lib/set-utils";
import type { EmploymentType, ExperienceLevel, JobPublic, WorkArrangement } from "@/lib/api/generated";

type JobAlertsPanelProps = {
  jobs: JobPublic[];
  companyNameById?: Record<string, string>;
};

const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3.5 py-2.5 text-sm text-zinc-900 shadow-sm focus:border-cdtm focus:outline-none focus:ring-2 focus:ring-cdtm/20";

const labelClass = "text-ui-title mb-1.5 block text-sm";

function toggleInSet<T>(set: Set<T>, value: T): Set<T> {
  return toggleSetValue(set, value);
}

function criteriaFromSets(
  query: string,
  arrangements: Set<WorkArrangement>,
  levels: Set<ExperienceLevel>,
  employment: Set<EmploymentType>,
): JobAlertCriteria {
  return {
    query,
    arrangements: [...arrangements],
    levels: [...levels],
    employment: [...employment],
  };
}

function CriteriaCheckboxes<T extends string>({
  title,
  options,
  selected,
  onToggle,
  format = (v) => v,
}: {
  title: string;
  options: readonly T[];
  selected: Set<T>;
  onToggle: (value: T) => void;
  format?: (value: T) => string;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-section-label">{title}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((value) => (
          <label
            key={value}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
              selected.has(value)
                ? "border-cdtm/30 bg-cdtm/[0.05] font-medium text-cdtm"
                : "border-zinc-200 text-zinc-700 hover:border-zinc-300"
            }`}
          >
            <input
              type="checkbox"
              checked={selected.has(value)}
              onChange={() => onToggle(value)}
              className="accent-cdtm"
            />
            {format(value)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function JobAlertsPanel({ jobs, companyNameById = {} }: JobAlertsPanelProps) {
  const [alerts, setAlerts] = useState<JobAlertRecord[]>([]);
  const [subscriberName, setSubscriberName] = useState("");
  const [email, setEmail] = useState("");
  const [alertLabel, setAlertLabel] = useState("");
  const [alertLabelTouched, setAlertLabelTouched] = useState(false);
  const [query, setQuery] = useState("");
  const [arrangements, setArrangements] = useState<Set<WorkArrangement>>(new Set());
  const [levels, setLevels] = useState<Set<ExperienceLevel>>(new Set());
  const [employment, setEmployment] = useState<Set<EmploymentType>>(new Set());
  const [cadence, setCadence] = useState<AlertCadence>("weekly");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setAlerts(loadJobAlerts());
    const prefs = loadSubscriberPrefs();
    setEmail(prefs.email);
    setSubscriberName(prefs.subscriberName);
  }, []);

  useEffect(() => {
    const nameInput = document.getElementById("alert-name");
    if (nameInput instanceof HTMLElement) {
      nameInput.focus();
    }
  }, []);

  const previewCriteria = useMemo(
    () => criteriaFromSets(query, arrangements, levels, employment),
    [query, arrangements, levels, employment],
  );

  const matchCount = useMemo(
    () => countMatchingJobs(jobs, previewCriteria, companyNameById),
    [jobs, previewCriteria, companyNameById],
  );

  function suggestPersonalizedLabel() {
    if (!alertLabelTouched) {
      setAlertLabel(
        subscriberName.trim()
          ? personalizedAlertLabel(subscriberName, previewCriteria)
          : defaultAlertLabel(previewCriteria),
      );
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    const trimmedName = subscriberName.trim();
    const trimmedEmail = email.trim();
    const trimmedLabel = alertLabel.trim();

    if (!trimmedName) {
      setError("Enter your name so we can personalize this alert.");
      return;
    }
    if (!trimmedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setError("Enter a valid email address.");
      return;
    }
    if (!trimmedLabel) {
      setError("Give this alert a short name (e.g. Sophie · remote product roles).");
      return;
    }

    const hasCriteria =
      previewCriteria.query.trim().length > 0 ||
      previewCriteria.arrangements.length > 0 ||
      previewCriteria.levels.length > 0 ||
      previewCriteria.employment.length > 0;

    if (!hasCriteria) {
      setError("Choose at least one job preference: keywords or a filter below.");
      return;
    }

    const alert = createJobAlert({
      subscriberName: trimmedName,
      email: trimmedEmail,
      alertLabel: trimmedLabel,
      cadence,
      ...previewCriteria,
    });

    setAlerts((prev) => [alert, ...prev]);
    setSaved(true);
  }

  function handleRemove(id: string) {
    removeJobAlert(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <div className="space-y-8">
      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-section-label">Your profile</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="alert-name" className={labelClass}>
                Full name
              </label>
              <input
                id="alert-name"
                type="text"
                value={subscriberName}
                onChange={(e) => {
                  setSubscriberName(e.target.value);
                  setSaved(false);
                }}
                onBlur={suggestPersonalizedLabel}
                placeholder="Sophie Klein"
                className={inputClass}
                autoComplete="name"
              />
            </div>
            <div>
              <label htmlFor="alert-email" className={labelClass}>
                Email
              </label>
              <input
                id="alert-email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setSaved(false);
                }}
                placeholder="sophie.klein@example.com"
                className={inputClass}
                autoComplete="email"
              />
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-section-label">Jobs you want</h2>
          <p className="mt-2 text-sm leading-relaxed text-zinc-600">
            Pick keywords and filters. We&apos;ll show how many open roles match right now.
          </p>

          <div className="mt-5 space-y-5">
            <div>
              <label htmlFor="alert-label" className={labelClass}>
                Alert name
              </label>
              <input
                id="alert-label"
                type="text"
                value={alertLabel}
                onChange={(e) => {
                  setAlertLabel(e.target.value);
                  setAlertLabelTouched(true);
                  setSaved(false);
                }}
                placeholder="Sophie · hybrid strategy roles"
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="alert-keywords" className={labelClass}>
                Keywords
              </label>
              <input
                id="alert-keywords"
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSaved(false);
                }}
                onBlur={suggestPersonalizedLabel}
                placeholder="e.g. product, python, munich"
                className={inputClass}
              />
            </div>

            <CriteriaCheckboxes
              title="Work arrangement"
              options={WORK_ARRANGEMENTS}
              selected={arrangements}
              onToggle={(v) => {
                setArrangements((prev) => toggleInSet(prev, v));
                setSaved(false);
              }}
              format={formatLabel}
            />
            <CriteriaCheckboxes
              title="Experience"
              options={EXPERIENCE_LEVELS}
              selected={levels}
              onToggle={(v) => {
                setLevels((prev) => toggleInSet(prev, v));
                setSaved(false);
              }}
              format={formatLabel}
            />
            <CriteriaCheckboxes
              title="Employment"
              options={EMPLOYMENT_TYPES}
              selected={employment}
              onToggle={(v) => {
                setEmployment((prev) => toggleInSet(prev, v));
                setSaved(false);
              }}
              format={formatLabel}
            />

            <p className="rounded-lg border border-zinc-200 bg-zinc-50/80 px-4 py-3 text-sm text-zinc-600">
              <span className="font-semibold text-zinc-900">{matchCount}</span>{" "}
              {matchCount === 1 ? "role matches" : "roles match"} now · watching:{" "}
              {describeAlertCriteria(previewCriteria)}
            </p>
          </div>
        </section>

        <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-6">
          <label htmlFor="alert-cadence" className={labelClass}>
            Frequency
          </label>
          <select
            id="alert-cadence"
            value={cadence}
            onChange={(e) => setCadence(e.target.value as AlertCadence)}
            className={inputClass}
          >
            <option value="weekly">Weekly digest</option>
            <option value="daily">Daily digest</option>
          </select>
        </section>

        {error && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            {error}
          </p>
        )}

        {saved && (
          <p className="rounded-lg border border-cdtm/20 bg-cdtm/[0.05] px-4 py-3 text-sm font-medium text-cdtm" role="status">
            Saved &ldquo;{alertLabel.trim()}&rdquo; for {subscriberName.trim()}. A{" "}
            {cadenceLabel(cadence).toLowerCase()} would go to {email.trim()} in production.
          </p>
        )}

        <button
          type="submit"
          className="w-full rounded-lg bg-cdtm px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-cdtm-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2 sm:w-auto"
        >
          Save personalized alert
        </button>
      </form>

      {alerts.length > 0 && (
        <section aria-labelledby="saved-alerts-heading">
          <h2 id="saved-alerts-heading" className="text-section-label">
            Your saved alerts
          </h2>
          <ul className="mt-3 space-y-2" role="list">
            {alerts.map((alert) => (
              <li
                key={alert.id}
                className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-zinc-900">
                      {alert.alertLabel || defaultAlertLabel(alert)}
                    </p>
                    <p className="mt-0.5 text-xs text-zinc-600">
                      {alert.subscriberName || "Subscriber"} · {alert.email}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {cadenceLabel(alert.cadence)} · {describeAlertCriteria(alert)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemove(alert.id)}
                    className="shrink-0 text-xs font-medium text-zinc-500 hover:text-cdtm"
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
