import { LoadingBlock } from "@/components/placeholders";

/**
 * The board reads jobs, companies and the members inside them, so it is one
 * of the slower pages, and worth a skeleton rather than a blank frame.
 */
export default function Loading() {
    return (
        <div className="shell-wide py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading roles" rows={5} />
            </div>
        </div>
    );
}
