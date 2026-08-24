"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../client";
import { qk } from "../keys";
import type { DevLoginResponse } from "@/auth/contract";

/**
 * The two dev sign-in calls, on the typed client like everything else.
 *
 * They used to be hand-rolled `fetch`es in the login screen and the auth
 * provider, each with its own idea of how to read an error body. Going through
 * `api` and `unwrap` means the paths are declared once, the error envelope is
 * parsed by `api/errors.ts`, and a backend rename is a compile error rather
 * than a 404 at sign-in.
 *
 * Neither call carries a token: they are what a visitor uses *before* they
 * have one.
 */

/** Type-ahead over the roster, for the optional "sign in as" picker. */
export function useDevMembers(query: string) {
    const trimmed = query.trim();
    return useQuery({
        queryKey: qk.devMembers(trimmed),
        queryFn: () =>
            unwrap(api.GET("/api/v1/auth/dev/members", { params: { query: { q: trimmed } } })),
        enabled: trimmed.length > 0,
        // The roster does not move during a sign-in, so a repeat of the same
        // prefix should not cost a request.
        staleTime: 5 * 60 * 1000,
        retry: false,
    });
}

/** Trade a CDTM address, or a roster slug, for an access token. */
export function devLogin(email: string, memberSlug: string | null): Promise<DevLoginResponse> {
    // The slug is the identifier the backend wants, and it reads the address
    // off that roster row itself. Sending the typed address alongside it is a
    // 409 whenever the two name different people, so only one of them travels.
    const body = memberSlug ? { member_slug: memberSlug } : { email };
    return unwrap(api.POST("/api/v1/auth/dev/login", { body }));
}
