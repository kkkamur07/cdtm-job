import { LoadingBlock } from "@/components/placeholders";

/**
 * One listing, its poster, and who else is in that city.
 */
export default function Loading() {
    return (
        <div className="shell-wide py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading listing" rows={4} />
            </div>
        </div>
    );
}
