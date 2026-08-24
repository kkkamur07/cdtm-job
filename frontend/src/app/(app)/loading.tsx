import { LoadingBlock } from "@/components/placeholders";

/**
 * The fallback for any route in the app shell that has not shipped its own.
 * Next renders it as soon as a navigation starts, so the shell stays put and
 * only the page area is replaced.
 */
export default function Loading() {
    return (
        <div className="shell-wide py-4 pb-12">
            <div className="card p-6">
                <LoadingBlock label="Loading" rows={4} />
            </div>
        </div>
    );
}
