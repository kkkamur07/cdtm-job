import { LoadingBlock } from "@/components/placeholders";

/**
 * Whichever composer this route is standing in for.
 */
export default function Loading() {
    return (
        <div className="shell py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading" rows={3} />
            </div>
        </div>
    );
}
