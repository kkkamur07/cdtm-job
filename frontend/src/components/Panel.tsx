import Link from "next/link";

/**
 * A titled card with an optional link in the corner. The home feed is a stack
 * of these, so the heading rhythm is defined once instead of per panel.
 */
export default function Panel({
    title,
    action,
    badge,
    children,
}: {
    title: string;
    action?: { href: string; label: string };
    badge?: number;
    children: React.ReactNode;
}) {
    return (
        <section className="card panel">
            <div className="panel-h">
                <h2 className="flex items-center gap-1.5">
                    {title}
                    {badge !== undefined && badge > 0 && (
                        <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[var(--radius-pill)] bg-blue px-1.5 text-[10.5px] font-semibold text-white">
                            {badge}
                        </span>
                    )}
                </h2>
                {action && (
                    <Link href={action.href} className="text-[12.5px] font-medium text-blue hover:underline">
                        {action.label}
                    </Link>
                )}
            </div>
            {children}
        </section>
    );
}
