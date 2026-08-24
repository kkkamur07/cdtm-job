import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { cache } from "react";

import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL, isSupabaseConfigured } from "./env";

/**
 * Server-side Supabase client, backed by the request's cookies.
 *
 * Never call this at module scope: the cookie store belongs to one request, and
 * holding it in a module variable would leak one visitor's session into
 * another's render.
 */
export async function createSupabaseServerClient() {
    if (!isSupabaseConfigured) return null;
    const cookieStore = await cookies();

    return createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
        cookies: {
            getAll() {
                return cookieStore.getAll();
            },
            // The second argument carries cache headers that keep a CDN from
            // storing a response with somebody's Set-Cookie on it. A Server
            // Component cannot set response headers, so they are dropped here
            // and applied by the proxy instead.
            setAll(cookiesToSet) {
                try {
                    for (const { name, value, options } of cookiesToSet) {
                        cookieStore.set(name, value, options);
                    }
                } catch {
                    // Server Components cannot set cookies. That is fine here:
                    // the proxy refreshes the session on every request, so the
                    // rotated cookies are already on the response.
                }
            },
        },
    });
}

export type ServerAuth = {
    /** Verified from a signature-checked JWT, not a decoded cookie. */
    userId: string | null;
    email: string | null;
    /** Forwarded to the FastAPI backend as a bearer token. */
    accessToken: string | null;
};

/**
 * Who is making this request, verified.
 *
 * `getClaims()` checks the token's signature against the project's published
 * keys, so its claims can be authorized on. `getSession()` only decodes
 * whatever the cookie says, so its user is never trusted here: it is read
 * purely to get the raw token string, which is both what the API is sent and
 * what is handed to `getClaims` to verify.
 *
 * The session is read once. `getClaims()` called with no argument reads it
 * again internally, so passing the token in is one cookie decode rather than
 * three.
 *
 * Wrapped in `React.cache` so every loader in one render shares a single
 * verification rather than each doing its own.
 */
export const getServerAuth = cache(async (): Promise<ServerAuth> => {
    const empty: ServerAuth = { userId: null, email: null, accessToken: null };

    const supabase = await createSupabaseServerClient();
    if (!supabase) return empty;

    const {
        data: { session },
    } = await supabase.auth.getSession();
    if (!session) return empty;

    const { data } = await supabase.auth.getClaims(session.access_token);
    const claims = data?.claims;
    if (!claims) return empty;

    return {
        userId: typeof claims.sub === "string" ? claims.sub : null,
        email: typeof claims.email === "string" ? claims.email : null,
        accessToken: session.access_token,
    };
});
