/**
 * Which sign-in this build uses.
 *
 * There is no Supabase project yet, so the app ships with a dev mode that
 * trades a CDTM e-mail address for a backend-issued token. The Supabase path
 * is complete and switched on by setting NEXT_PUBLIC_AUTH_MODE=supabase (or by
 * simply having NEXT_PUBLIC_SUPABASE_URL set); nothing else in the app changes,
 * because both modes end up handing the same bearer token to the same API.
 */
export type AuthMode = "dev" | "supabase";

/**
 * Dev mode is passwordless: anything ending in @cdtm.com becomes a session,
 * and passing a roster slug becomes that Member. That is a development
 * convenience and never an acceptable production login, so a production build
 * refuses it outright rather than falling back to it when the Supabase
 * variables are missing. An unconfigured production build lands on
 * "Supabase is not configured" at /login, which is a dead end on purpose: a
 * dead end is the safe failure, an open door is not.
 */
function resolve(): AuthMode {
    if (process.env.NODE_ENV === "production") return "supabase";

    const explicit = process.env.NEXT_PUBLIC_AUTH_MODE;
    if (explicit === "supabase" || explicit === "dev") return explicit;
    return process.env.NEXT_PUBLIC_SUPABASE_URL ? "supabase" : "dev";
}

export const AUTH_MODE: AuthMode = resolve();
export const isDevAuth = AUTH_MODE === "dev";
export const isSupabaseAuth = AUTH_MODE === "supabase";

/** Name of the httpOnly cookie the dev session lives in. */
export const DEV_SESSION_COOKIE = "cdtm_dev_session";
