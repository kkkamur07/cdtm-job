"use client";

/**
 * The last line of defence.
 *
 * Almost everything on these pages is fetched on the server, so the usual cause
 * of landing here is that the API did not answer. Saying so is more useful than
 * "something went wrong", because the fix is usually to start the backend.
 */
export default function AppError({ error, reset }: { error: Error; reset: () => void }) {
    return (
        <div className="shell py-16">
            <div className="card mx-auto max-w-[34rem] p-6">
                <h1 className="text-lg font-semibold">That page did not load</h1>
                <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
                    {error.message || "The API did not answer."} Check that the backend is running
                    at the address in <code className="font-mono text-[12.5px]">NEXT_PUBLIC_API_URL</code>,
                    then try again.
                </p>
                <button type="button" className="btn btn-blue mt-4" onClick={reset}>
                    Try again
                </button>
            </div>
        </div>
    );
}
