import type { EmploymentType, ExperienceLevel, WorkArrangement } from "@/lib/api/generated";
import {
  EMPLOYMENT_TYPES,
  EXPERIENCE_LEVELS,
  formatLabel,
  WORK_ARRANGEMENTS,
} from "@/lib/format-job";

export { EMPLOYMENT_TYPES, EXPERIENCE_LEVELS, WORK_ARRANGEMENTS };

const ALERTS_KEY = "cdtm-job-board-alerts";
const SUBSCRIBER_KEY = "cdtm-job-board-alert-subscriber";

export type AlertCadence = "weekly" | "daily";

export type JobAlertCriteria = {
  query: string;
  arrangements: WorkArrangement[];
  levels: ExperienceLevel[];
  employment: EmploymentType[];
};

export type JobAlertRecord = JobAlertCriteria & {
  id: string;
  email: string;
  subscriberName: string;
  alertLabel: string;
  cadence: AlertCadence;
  createdAt: string;
};

export type AlertSubscriberPrefs = {
  email: string;
  subscriberName: string;
};

function isBrowser() {
  return typeof window !== "undefined";
}

function normalizeAlert(raw: JobAlertRecord): JobAlertRecord {
  return {
    ...raw,
    subscriberName: raw.subscriberName ?? "",
    alertLabel: raw.alertLabel ?? "",
    query: raw.query ?? "",
    arrangements: raw.arrangements ?? [],
    levels: raw.levels ?? [],
    employment: raw.employment ?? [],
  };
}

export function loadJobAlerts(): JobAlertRecord[] {
  if (!isBrowser()) return [];
  try {
    const raw = window.localStorage.getItem(ALERTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as JobAlertRecord[];
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeAlert);
  } catch {
    return [];
  }
}

export function persistJobAlerts(alerts: JobAlertRecord[]) {
  if (!isBrowser()) return;
  window.localStorage.setItem(ALERTS_KEY, JSON.stringify(alerts));
}

export function loadSubscriberPrefs(): AlertSubscriberPrefs {
  if (!isBrowser()) return { email: "", subscriberName: "" };
  try {
    const raw = window.localStorage.getItem(SUBSCRIBER_KEY);
    if (!raw) return { email: "", subscriberName: "" };
    const parsed = JSON.parse(raw) as AlertSubscriberPrefs;
    return {
      email: parsed.email ?? "",
      subscriberName: parsed.subscriberName ?? "",
    };
  } catch {
    return { email: "", subscriberName: "" };
  }
}

export function saveSubscriberPrefs(prefs: AlertSubscriberPrefs) {
  if (!isBrowser()) return;
  window.localStorage.setItem(SUBSCRIBER_KEY, JSON.stringify(prefs));
}

export function createJobAlert(
  input: Omit<JobAlertRecord, "id" | "createdAt">,
): JobAlertRecord {
  const alert: JobAlertRecord = {
    ...input,
    id: generateAlertId(),
    createdAt: new Date().toISOString(),
  };
  persistJobAlerts([alert, ...loadJobAlerts()]);
  saveSubscriberPrefs({ email: input.email, subscriberName: input.subscriberName });
  return alert;
}

export function removeJobAlert(id: string) {
  persistJobAlerts(loadJobAlerts().filter((a) => a.id !== id));
}

export function describeAlertCriteria(alert: JobAlertCriteria): string {
  const parts: string[] = [];
  if (alert.query.trim()) parts.push(`keywords “${alert.query.trim()}”`);
  alert.arrangements.forEach((v) => parts.push(formatLabel(v)));
  alert.levels.forEach((v) => parts.push(formatLabel(v)));
  alert.employment.forEach((v) => parts.push(formatLabel(v)));
  return parts.length > 0 ? parts.join(", ") : "all open roles";
}

export function cadenceLabel(cadence: AlertCadence): string {
  return cadence === "weekly" ? "Weekly digest" : "Daily digest";
}

export function defaultAlertLabel(criteria: JobAlertCriteria): string {
  const summary = describeAlertCriteria(criteria);
  if (summary === "all open roles") return "All open roles";
  return summary.length > 48 ? `${summary.slice(0, 45)}…` : summary;
}

/** e.g. "Sophie · hybrid, senior" */
export function personalizedAlertLabel(
  subscriberName: string,
  criteria: JobAlertCriteria,
): string {
  const first = subscriberName.trim().split(/\s+/)[0];
  const summary = describeAlertCriteria(criteria);
  if (!first) return defaultAlertLabel(criteria);
  if (summary === "all open roles") return `${first}'s job matches`;
  const short =
    summary.length > 40 ? `${summary.slice(0, 37)}…` : summary;
  return `${first} · ${short}`;
}

function generateAlertId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `alert-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}
