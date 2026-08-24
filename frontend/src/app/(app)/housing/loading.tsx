import { LoadingBlock } from "@/components/placeholders";

/**
 * The board plus the filters it is drawn from.
 */
export default function Loading() {
    return (
        <div className="shell-wide py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading listings" rows={5} />
            </div>
        </div>
    );
}
