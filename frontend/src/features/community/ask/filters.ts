import { INTENTS } from "@/lib/intents";
import { badgeLabel } from "@/lib/format";

/**
 * Turning an interpretation's filter object into chips.
 *
 * The three Ask endpoints answer with three different filter shapes, and the
 * UI shows all of them the same way: one chip per filter that was set, in a
 * fixed order so the same question always reads the same. Anything the backend
 * adds later shows up automatically under its own key rather than disappearing.
 */

export type Chip = { key: string; label: string; tone: "intent" | "place" | "plain" };

/** Keys that never belong on a chip: they are paging, not meaning. */
const HIDDEN = new Set(["limit", "sort", "skip"]);

/** The order chips read best in, most identifying first. */
const ORDER = [
    "intents",
    "kind",
    "employment_type",
    "work_arrangement",
    "experience_level",
    "location",
    "city",
    "district",
    "country",
    "company",
    "past_company",
    "title",
    "study_group",
    "first_step_group",
    "current_group",
    "school",
    "degree",
    "major",
    "class_label",
    "skills",
    "languages",
    "roles",
    "q",
];

const PLACE_KEYS = new Set(["location", "city", "district", "country"]);

const LABELS: Record<string, (value: string) => string> = {
    intents: (value) => `Open to ${intentLabel(value)}`,
    q: (value) => `“${value}”`,
    class_year_min: (value) => `Class ${value} or later`,
    class_year_max: (value) => `Class ${value} or earlier`,
    min_price: (value) => `From € ${value}`,
    max_price: (value) => `Under € ${value}`,
    min_rooms: (value) => `${value}+ rooms`,
    salary_min: (value) => `From € ${value}`,
    posted_within_days: (value) => `Posted in the last ${value} days`,
    employment_type: badgeLabel,
    work_arrangement: badgeLabel,
    experience_level: badgeLabel,
    kind: (value) => (value === "offer" ? "Offering" : "Looking"),
    is_ca: (value) => (value === "true" ? "Centre Assistant" : "Not a Centre Assistant"),
    is_cdtm_startup: (value) => (value === "true" ? "CDTM startup" : "Not a CDTM startup"),
    remote_only: (value) => (value === "true" ? "Remote only" : "Not remote only"),
    furnished: (value) => (value === "true" ? "Furnished" : "Unfurnished"),
};

function intentLabel(value: string): string {
    return INTENTS.find((item) => item.key === value)?.label.toLowerCase() ?? value;
}

/** Turns a key like `first_step_group` into "First step group" for the fallback. */
function keyLabel(key: string): string {
    const words = key.replaceAll("_", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}

export function filterChips(filters: Record<string, unknown> | null | undefined): Chip[] {
    if (!filters) return [];

    const chips: Chip[] = [];
    const keys = Object.keys(filters).sort((a, b) => {
        const ai = ORDER.indexOf(a);
        const bi = ORDER.indexOf(b);
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });

    for (const key of keys) {
        if (HIDDEN.has(key)) continue;
        const raw = filters[key];
        if (raw === null || raw === undefined || raw === "") continue;
        if (Array.isArray(raw) && raw.length === 0) continue;

        const values = Array.isArray(raw) ? raw.map(String) : [String(raw)];
        for (const value of values) {
            const label = LABELS[key]?.(value) ?? `${keyLabel(key)}: ${value}`;
            chips.push({
                key: `${key}:${value}`,
                label,
                tone: key === "intents" ? "intent" : PLACE_KEYS.has(key) ? "place" : "plain",
            });
        }
    }

    return chips;
}

/**
 * Why a given member is in the answer.
 *
 * The API ranks and returns; it does not say per row which filter each person
 * satisfied. Rather than invent a reason, this compares the row against the
 * filters that were actually applied and reports only what it can see: the
 * place, the intent, the company or the phrase that appears in their headline.
 * A row with nothing visible to point at gets no line at all.
 */
export type MatchReason = { prefix: string; highlight: string };

export function whyMatched(
    member: {
        location?: string | null;
        company?: string | null;
        title?: string | null;
        headline?: string | null;
        intents?: Record<string, unknown> | null;
        class_label?: string | null;
    },
    filters: Record<string, unknown> | null | undefined,
): MatchReason[] {
    if (!filters) return [];
    const reasons: MatchReason[] = [];

    const location = asString(filters.location);
    if (location && member.location?.toLowerCase().includes(location.toLowerCase())) {
        reasons.push({ prefix: "Based in", highlight: location });
    }

    const intents = asArray(filters.intents);
    for (const intent of intents) {
        if (member.intents && member.intents[intent] === true) {
            reasons.push({ prefix: "Open to", highlight: intentLabel(intent) });
        }
    }

    const company = asString(filters.company) ?? asString(filters.past_company);
    if (company && member.company?.toLowerCase().includes(company.toLowerCase())) {
        reasons.push({ prefix: "Works at", highlight: member.company });
    }

    const title = asString(filters.title);
    if (title && member.title?.toLowerCase().includes(title.toLowerCase())) {
        reasons.push({ prefix: "Title matches", highlight: title });
    }

    const haystack = `${member.headline ?? ""} ${member.title ?? ""} ${member.company ?? ""}`.toLowerCase();
    for (const skill of [...asArray(filters.skills), ...asArray(filters.languages)]) {
        if (haystack.includes(skill.toLowerCase())) {
            reasons.push({ prefix: "Mentions", highlight: skill });
        }
    }

    const classLabel = asString(filters.class_label);
    if (classLabel && member.class_label === classLabel) {
        reasons.push({ prefix: "Class", highlight: classLabel });
    }

    return reasons.slice(0, 3);
}

function asString(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

function asArray(value: unknown): string[] {
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
