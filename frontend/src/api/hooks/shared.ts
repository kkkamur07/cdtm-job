"use client";

import { useSession } from "@/auth/AuthProvider";
import { ApiError } from "../errors";

/**
 * Options shared by every query that needs a bearer token.
 *
 * Two things matter here: the query must not fire before the Supabase SDK has
 * restored the session (otherwise the first call goes out unauthenticated and
 * 401s), and a 401/403 must not be retried, because retrying cannot change the
 * answer and only delays the sign-in screen.
 */
export function useAuthedQueryOptions() {
    const { signedIn, loading } = useSession();
    return {
        enabled: !loading && signedIn,
        retry: (failureCount: number, error: Error) => {
            if (error instanceof ApiError && (error.isAuth || error.isForbidden || error.isNotFound)) {
                return false;
            }
            return failureCount < 2;
        },
    };
}

/**
 * Public reads (jobs, companies) work signed out, so they only need the retry
 * policy.
 */
export function usePublicQueryOptions() {
    return {
        retry: (failureCount: number, error: Error) => {
            if (error instanceof ApiError && error.isNotFound) return false;
            return failureCount < 2;
        },
    };
}
