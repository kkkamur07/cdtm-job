import { LoadingBlock } from "@/components/placeholders";

/**
 * The flow diagram is computed over every member, so this is the page most
 * likely to be waited on.
 */
export default function Loading() {
    return (
        <div className="shell-wide py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading paths" rows={4} />
            </div>
        </div>
    );
}
