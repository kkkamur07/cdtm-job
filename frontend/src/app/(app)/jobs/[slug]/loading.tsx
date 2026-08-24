import { LoadingBlock } from "@/components/placeholders";

/**
 * One role, its company and whoever posted it.
 */
export default function Loading() {
    return (
        <div className="shell py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading role" rows={4} />
            </div>
        </div>
    );
}
