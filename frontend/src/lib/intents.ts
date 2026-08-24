import type { Intents } from "@/api/types";

/**
 * The six things a member can be open to. The keys are exactly the boolean
 * fields on IntentsPublic and the values the members search accepts as
 * `?intent=`, so the filter chips and the edit form stay in step by
 * construction.
 */
export type IntentKey =
    | "cofounding"
    | "mentoring"
    | "hiring"
    | "open_to_roles"
    | "investing"
    | "speaking";

export const INTENTS: { key: IntentKey; label: string; description: string }[] = [
    { key: "cofounding", label: "Co-founding", description: "Looking for or open to co-founders" },
    { key: "mentoring", label: "Mentoring", description: "Happy to mentor students and recent grads" },
    { key: "hiring", label: "Hiring", description: "My team or company is hiring" },
    { key: "open_to_roles", label: "Open to roles", description: "Quietly or actively looking" },
    { key: "investing", label: "Investing", description: "Angel cheques or fund investments" },
    { key: "speaking", label: "Speaking", description: "Talks, panels, guest lectures" },
];

export const INTENT_LABEL: Record<IntentKey, string> = Object.fromEntries(
    INTENTS.map((i) => [i.key, i.label]),
) as Record<IntentKey, string>;

/** The intents a member has switched on, in the canonical display order. */
export function activeIntents(intents: Intents | null | undefined): IntentKey[] {
    if (!intents) return [];
    return INTENTS.filter((i) => intents[i.key]).map((i) => i.key);
}
