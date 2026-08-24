import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { isSupabaseAuth } from "@/auth/mode";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL, isSupabaseConfigured } from "./env";

/**
 * Refreshes the Supabase session on every request and writes the rotated
 * cookies onto the response.
 *
 * Without this, an expired access token is only noticed in the browser, and
 * server components render as signed out for a visitor who is signed in.
 *
 * This is the only place a rotated session is written back: a Server Component
 * refreshing through `lib/supabase/server` swallows its `cookieStore.set`,
 * because a component cannot set a header on a response that is already
 * streaming. So every request that can render a Server Component has to come
 * through here, prefetches included. A prefetch is an ordinary same-origin
 * `fetch()` whose `Set-Cookie` the browser applies; skipping it would let the
 * prefetched render rotate the refresh token and drop the new one, which signs
 * the visitor out on their next real navigation.
 *
 * This app has public pages (jobs, companies), so nothing is redirected here.
 * Pages that need a member decide that for themselves.
 */
export async function updateSession(request: NextRequest): Promise<NextResponse> {
    let response = NextResponse.next({ request });

    // A dev-auth build has no Supabase session to refresh; its token lives in
    // an httpOnly cookie this never touches. In production the mode is always
    // supabase, so this only ever skips a local dev build.
    if (!isSupabaseAuth || !isSupabaseConfigured) return response;

    // Created per request. A client kept in a module variable would be shared
    // between visitors on a warm serverless instance.
    const supabase = createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
        cookies: {
            getAll() {
                return request.cookies.getAll();
            },
            setAll(cookiesToSet, headers) {
                for (const { name, value } of cookiesToSet) {
                    request.cookies.set(name, value);
                }
                response = NextResponse.next({ request });
                for (const { name, value, options } of cookiesToSet) {
                    response.cookies.set(name, value, options);
                }
                // Cache-Control and friends, so no CDN stores a response that
                // carries someone else's refreshed session cookie.
                for (const [key, value] of Object.entries(headers ?? {})) {
                    response.headers.set(key, value);
                }
            },
        },
    });

    // IMPORTANT: nothing may run between createServerClient and this call.
    // Any await in between can let the response be sent before the refreshed
    // cookies are attached, which logs the visitor out at random.
    await supabase.auth.getClaims();

    return response;
}
