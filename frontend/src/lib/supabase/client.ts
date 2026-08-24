"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL, isSupabaseConfigured } from "./env";

/**
 * The browser Supabase client.
 *
 * `createBrowserClient` from @supabase/ssr stores the session in cookies rather
 * than localStorage, which is what lets the middleware refresh it and server
 * components read it. Swapping this for supabase-js `createClient` would put
 * the session somewhere the server cannot see.
 *
 * It is a singleton: a second client would run a second refresh timer and the
 * two would race to rotate the same refresh token.
 */
let browserClient: SupabaseClient | null = null;

export function getSupabaseBrowserClient(): SupabaseClient | null {
    if (!isSupabaseConfigured) return null;
    if (!browserClient) {
        browserClient = createBrowserClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
    }
    return browserClient;
}
