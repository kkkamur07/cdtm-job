import type { Intents } from "@/api/types";
import { INTENT_LABEL, activeIntents } from "@/lib/intents";

/** What a member is open to, as pills. Renders nothing when they are open to nothing. */
export default function IntentPills({
    intents,
    max = 4,
    className = "",
}: {
    intents: Intents | null | undefined;
    max?: number;
    className?: string;
}) {
    const keys = activeIntents(intents);
    if (!keys.length) return null;

    const shown = keys.slice(0, max);
    const rest = keys.length - shown.length;

    return (
        <span className={`flex flex-wrap items-center gap-1 ${className}`}>
            {shown.map((key) => (
                <span key={key} className="pill pill-intent">
                    {INTENT_LABEL[key]}
                </span>
            ))}
            {rest > 0 && <span className="pill pill-muted">+{rest}</span>}
        </span>
    );
}
