"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "@/api/errors";
import { AuthProvider } from "@/auth/AuthProvider";

export default function Providers({
    children,
    initialEmail = null,
    initialSignedIn = false,
}: {
    children: React.ReactNode;
    initialEmail?: string | null;
    initialSignedIn?: boolean;
}) {
    // Created in state, not at module scope: one client per browser tab, and
    // never one shared between requests during SSR.
    const [client] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 30_000,
                        refetchOnWindowFocus: false,
                        retry: (failureCount, error) => {
                            // A 4xx will not become a 2xx by asking again.
                            if (error instanceof ApiError && error.status < 500) return false;
                            return failureCount < 2;
                        },
                    },
                },
            }),
    );

    return (
        <QueryClientProvider client={client}>
            <AuthProvider initialEmail={initialEmail} initialSignedIn={initialSignedIn}>
                {children}
            </AuthProvider>
        </QueryClientProvider>
    );
}
