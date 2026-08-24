"use client";

/**
 * The boundary above the root layout.
 *
 * `app/(app)/error.tsx` catches anything thrown inside the shell. This catches
 * what it cannot: an error thrown by the root layout itself, which means there
 * is no shell, no providers and no stylesheet to rely on. It therefore renders
 * its own document and inlines the few styles it needs.
 *
 * The title is a React element rather than a metadata export, because metadata
 * is part of the layout that has just failed.
 */
export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
    return (
        <html lang="en">
            <body
                style={{
                    margin: 0,
                    minHeight: "100vh",
                    display: "grid",
                    placeItems: "center",
                    background: "#f6f6f4",
                    color: "#141414",
                    fontFamily:
                        "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif",
                }}
            >
                <title>Something went wrong · CDTM Community</title>
                <main style={{ maxWidth: "34rem", padding: "2rem", textAlign: "center" }}>
                    <h1 style={{ fontSize: "1.125rem", fontWeight: 600, margin: 0 }}>
                        CDTM Community could not start
                    </h1>
                    <p style={{ marginTop: "0.75rem", fontSize: "0.875rem", lineHeight: 1.6 }}>
                        {error.message || "The app failed before it could render anything."}
                    </p>
                    <button
                        type="button"
                        onClick={reset}
                        style={{
                            marginTop: "1.25rem",
                            border: "1px solid #d8d8d4",
                            borderRadius: "999px",
                            background: "#ffffff",
                            padding: "0.5rem 1.1rem",
                            fontSize: "0.8125rem",
                            fontWeight: 500,
                            cursor: "pointer",
                        }}
                    >
                        Try again
                    </button>
                </main>
            </body>
        </html>
    );
}
