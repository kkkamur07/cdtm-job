import Link from "next/link";

import type { MemberPath } from "@/api/types";

/**
 * One person's path in the cdtm-paths shape: what they studied, the first step
 * after CDTM, and where they are now. Three fixed steps rather than a full
 * timeline, because that is what the aggregate view on /paths is built from,
 * and seeing them in the same shape is what makes "who else went this way"
 * a sensible question to ask.
 */
export default function PathStrip({ path }: { path: MemberPath | null | undefined }) {
    if (!path || (!path.study_group && !path.first_step_group && !path.current_group)) {
        return (
            <p className="text-[13px] text-muted">
                No path computed for this member yet. Paths are derived from their studies and positions.
            </p>
        );
    }

    const steps = [
        {
            key: "Studied",
            group: path.study_group,
            detail: null as string | null,
            className: "bg-blue-soft border-transparent",
        },
        {
            key: "First step",
            group: path.first_step_group,
            detail: joined(path.first_step_title, path.first_step_company),
            className: "",
        },
        {
            key: "Now",
            group: path.current_group,
            detail: joined(path.current_title, path.current_company),
            className: "bg-green-soft border-green",
        },
    ].filter((step) => step.group);

    return (
        <div className="grid gap-2">
            <ol className="grid gap-2 sm:grid-cols-3">
                {steps.map((step) => (
                    <li key={step.key} className={`rounded-2xl border border-line bg-white p-3 ${step.className}`}>
                        <p className="text-[10px] font-semibold tracking-[0.08em] text-muted uppercase">
                            {step.key}
                        </p>
                        <p className="mt-1 text-[13px] leading-snug font-semibold">{step.group}</p>
                        {step.detail && <p className="mt-1 text-[11.5px] text-muted">{step.detail}</p>}
                    </li>
                ))}
            </ol>
            {path.current_group && (
                <p className="text-[12.5px]">
                    <Link href="/paths" className="font-medium text-blue hover:underline">
                        See everyone on this path
                    </Link>
                </p>
            )}
        </div>
    );
}

function joined(title?: string | null, company?: string | null): string | null {
    if (title && company) return `${title}, ${company}`;
    return title ?? company ?? null;
}
