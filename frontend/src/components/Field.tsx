import { useId } from "react";

/**
 * Label, control and hint as one unit. Every form in the app uses it, so the
 * label is always tied to its control by id and the hint is always announced
 * with it, without each form having to remember.
 */
export default function Field({
    label,
    hint,
    required,
    children,
}: {
    label: string;
    hint?: string;
    required?: boolean;
    children: (props: { id: string; "aria-describedby": string | undefined }) => React.ReactNode;
}) {
    const id = useId();
    const hintId = hint ? `${id}-hint` : undefined;

    return (
        <div>
            <label className="label" htmlFor={id}>
                {label}
                {required && <span className="ml-1 text-blue">*</span>}
            </label>
            {children({ id, "aria-describedby": hintId })}
            {hint && (
                <p id={hintId} className="mt-1.5 text-[12px] text-muted">
                    {hint}
                </p>
            )}
        </div>
    );
}

/** Two fields side by side above 640px, stacked below. */
export function FieldRow({ children }: { children: React.ReactNode }) {
    return <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
}
