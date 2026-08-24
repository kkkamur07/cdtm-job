import type { Education, Position } from "@/api/types";
import { safeUrl } from "@/lib/format";

/**
 * Positions and schooling as a rail with a dot per entry. Current roles get a
 * green dot, so "where are they now" is answerable at a glance without reading
 * the dates.
 *
 * The two section headings take their rank from the caller: the same view is
 * the whole page in one place and a panel inside one in another, and a heading
 * that is right in both is a heading the caller has to name.
 */
export default function MemberPositions({
    positions,
    educations,
    level = "h3",
}: {
    positions: Position[];
    educations?: Education[];
    level?: "h2" | "h3";
}) {
    const Heading = level;

    if (!positions.length && !educations?.length) {
        return <p className="text-[13px] text-muted">No positions on record.</p>;
    }

    return (
        <div className="grid gap-6">
            {positions.length > 0 && (
                <section>
                    <Heading className="mb-2.5 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">
                        Positions
                    </Heading>
                    <ol className="grid gap-3">
                        {positions.map((position, index) => {
                            const url = safeUrl(position.company_url);
                            return (
                                <li key={position.id ?? index} className="grid grid-cols-[18px_1fr] gap-2.5">
                                    <span className="relative" aria-hidden="true">
                                        <span
                                            className={`absolute top-[5px] left-[5px] h-[7px] w-[7px] rounded-full ${
                                                position.is_current ? "bg-green" : "bg-line"
                                            }`}
                                        />
                                        {index < positions.length - 1 && (
                                            <span className="absolute top-2 -bottom-3 left-2 w-px bg-line" />
                                        )}
                                    </span>
                                    <div className="min-w-0">
                                        <p className="text-[13.5px] font-semibold">
                                            {position.title ?? "Role"}
                                        </p>
                                        <p className="text-[12.5px] text-muted">
                                            {url ? (
                                                <a
                                                    href={url}
                                                    target="_blank"
                                                    rel="noreferrer noopener"
                                                    className="hover:text-blue hover:underline"
                                                >
                                                    {position.company}
                                                </a>
                                            ) : (
                                                position.company
                                            )}
                                            {position.date_range ? ` · ${position.date_range}` : ""}
                                        </p>
                                    </div>
                                </li>
                            );
                        })}
                    </ol>
                </section>
            )}

            {educations && educations.length > 0 && (
                <section>
                    <Heading className="mb-2.5 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">
                        Education
                    </Heading>
                    <ul className="grid gap-2">
                        {educations.map((school, index) => (
                            <li key={school.id ?? index}>
                                <p className="text-[13.5px] font-semibold">{school.school ?? "School"}</p>
                                <p className="text-[12.5px] text-muted">
                                    {[school.degree, school.date_range].filter(Boolean).join(" · ")}
                                </p>
                            </li>
                        ))}
                    </ul>
                </section>
            )}
        </div>
    );
}
