import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { DEV_SESSION_COOKIE, isDevAuth } from "./mode";

/**
 * The server's view of who is making this request, in whichever auth mode the
 * build runs in.
 *
 * Every server-side read goes through `getAccessToken()`, so switching between
 * dev sign-in and Supabase sign-in changes this file and nothing else.
 *
 * Wrapped in `React.cache`, so a page and all of its loaders verify once per
 * render rather than once per call.
 */

export type Identity = {
    email: string | null;
    userId: string | null;
    accessToken: string | null;
};

const anonymous: Identity = { email: null, userId: null, accessToken: null };

export const getIdentity = cache(async (): Promise<Identity> => {
    if (isDevAuth) {
        const store = await cookies();
        const raw = store.get(DEV_SESSION_COOKIE)?.value;
        if (!raw) return anonymous;
        try {
            const parsed = JSON.parse(Buffer.from(raw, "base64url").toString("utf8")) as {
                accessToken?: string;
                email?: string | null;
                expiresAt?: number | null;
            };
            if (!parsed.accessToken) return anonymous;
            if (parsed.expiresAt && parsed.expiresAt < Date.now()) return anonymous;
            return { email: parsed.email ?? null, userId: null, accessToken: parsed.accessToken };
        } catch {
            return anonymous;
        }
    }

    // Imported lazily so a dev-mode build never pulls the Supabase SSR client
    // into a render that has no use for it.
    const { getServerAuth } = await import("@/lib/supabase/server");
    const auth = await getServerAuth();
    return { email: auth.email, userId: auth.userId, accessToken: auth.accessToken };
});

export async function getAccessToken(): Promise<string | null> {
    return (await getIdentity()).accessToken;
}
