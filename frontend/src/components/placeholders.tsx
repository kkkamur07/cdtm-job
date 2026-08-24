/**
 * The two states that need no interactivity: "still loading" and "nothing
 * here".
 *
 * They live apart from `states.tsx` on purpose. That file is a client module
 * because `ErrorState` takes an `onRetry` callback, and importing it from a
 * server component used to drag these two skeletons into the browser bundle of
 * nineteen files that only ever draw them on the server. These are plain
 * markup, so a server component can render them and send nothing.
 */

/**
 * The rows depend on nothing but their count, and there are no hooks here to
 * memoize with (nor a compiler to do it), so the rendered arrays are built once
 * per distinct `rows` and reused. Twenty-one call sites pass a literal 2, 3 or
 * 4, so the cache stays at a handful of entries.
 */
const ROWS_BY_COUNT = new Map<number, React.ReactNode[]>();

function skeletonRows(count: number): React.ReactNode[] {
    let rows = ROWS_BY_COUNT.get(count);
    if (!rows) {
        rows = Array.from({ length: count }, (_, i) => (
            <div
                // The rows are identical and there are `count` of them, so the
                // position is the identity; nothing reorders here.
                key={`row-${i}`}
                className="h-14 animate-pulse rounded-2xl bg-line/50"
                style={{ animationDelay: `${i * 80}ms` }}
            />
        ));
        ROWS_BY_COUNT.set(count, rows);
    }
    return rows;
}

export function LoadingBlock({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
    return (
        <div role="status" aria-busy="true" aria-label={label} className="grid gap-2 p-3">
            <span className="sr-only">{label}</span>
            {skeletonRows(rows)}
        </div>
    );
}

export function EmptyState({
    title,
    hint,
    action,
}: {
    title: string;
    hint?: string;
    action?: React.ReactNode;
}) {
    return (
        <div className="grid justify-items-center gap-2 px-4 py-9 text-center">
            <p className="text-sm font-medium">{title}</p>
            {hint && <p className="max-w-[42ch] text-[13px] text-muted">{hint}</p>}
            {action}
        </div>
    );
}
