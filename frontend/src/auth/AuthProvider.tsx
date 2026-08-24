"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { setAccessToken } from "@/api/client";
import { errorMessage } from "@/api/errors";
import { devLogin } from "@/api/hooks/auth";
import { AUTH_MODE, isDevAuth, type AuthMode } from "./mode";
import type { DevLoginResponse, DevSession } from "./contract";

type AuthState = {
    mode: AuthMode;
    email: string | null;
    signedIn: boolean;
    /** True until the stored session has been restored or ruled out. */
    loading: boolean;
    /** False when the chosen mode has nothing to talk to (no Supabase URL). */
    configured: boolean;
    signInWithGoogle: (next?: string) => Promise<{ error: string | null }>;
    signInAsDev: (email: string, memberSlug?: string | null) => Promise<{ error: string | null }>;
    signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

/**
 * The access token lives in its own context.
 *
 * It is replaced on every silent refresh (Supabase renews roughly hourly, and
 * again when a tab regains focus), while `signedIn`, `email` and `loading` are
 * unchanged by a refresh. Keeping it in the same value would re-render every
 * `useAuthedQueryOptions` consumer on the page (two dozen save buttons on
 * /network) for a token none of them reads. One component reads it:
 * ImageUpload, which passes it to the media upload.
 */
const TokenContext = createContext<string | null>(null);

// The Supabase browser client is a chunk of its own, and `token` stays null
// until it lands, which holds back every query gated on a session. Starting the
// download when this module is evaluated puts it alongside hydration instead of
// one chunk round trip after it. `preloadModule` would be the tidier hint, but
// the bundler does not expose a stable chunk URL to name here, so the import is
// the hint. `typeof window` keeps the module out of the server graph, and a
// failed load is left to the effect below to report.
if (!isDevAuth && typeof window !== "undefined") {
    void import("@/lib/supabase/client").catch(() => {});
    void import("@/lib/supabase/env").catch(() => {});
}

/**
 * Holds the session and hands its access token to the API client.
 *
 * Both modes end in the same place: a bearer token the FastAPI backend
 * verifies. In Supabase mode it comes from the cookie-backed Supabase session;
 * in dev mode it is minted by the backend and parked in an httpOnly cookie by
 * /api/auth/dev-session, so the server can read it too. Client code never
 * branches on the mode: it reads `token`.
 */
export function AuthProvider({
    children,
    initialEmail = null,
    initialSignedIn = false,
}: {
    children: React.ReactNode;
    /**
     * Server-verified summary, so the first paint already knows whether
     * somebody is signed in and does not flash the signed-out state.
     */
    initialEmail?: string | null;
    initialSignedIn?: boolean;
}) {
    const router = useRouter();
    const [token, setToken] = useState<string | null>(null);
    const [email, setEmail] = useState<string | null>(initialEmail);
    const [signedIn, setSignedIn] = useState(initialSignedIn);
    const [loading, setLoading] = useState(true);
    const [configured, setConfigured] = useState(true);

    /**
     * One place where the session changes, so the API client and React state
     * are never out of step.
     *
     * The client is told first and synchronously. A query gated on `signedIn`
     * fires from a child component's effect, and a child's effects run before
     * its parent's, so publishing the token from an effect here would let the
     * first request of every session go out unauthenticated and 401.
     */
    const apply = useCallback((next: string | null, address: string | null) => {
        setAccessToken(next);
        setToken(next);
        setEmail(address);
        setSignedIn(Boolean(next));
        setLoading(false);
    }, []);

    /* ------------------------------------------------------- restore */

    useEffect(() => {
        let active = true;

        if (isDevAuth) {
            fetch("/api/auth/dev-session", { cache: "no-store" })
                .then((response) => (response.ok ? (response.json() as Promise<DevSession | null>) : null))
                .then((session) => {
                    if (!active) return;
                    apply(session?.accessToken ?? null, session?.email ?? null);
                })
                .catch(() => active && setLoading(false));
            return () => {
                active = false;
            };
        }

        let unsubscribe = () => {};
        void (async () => {
            const [{ getSupabaseBrowserClient }, { isSupabaseConfigured }] = await Promise.all([
                import("@/lib/supabase/client"),
                import("@/lib/supabase/env"),
            ]);
            if (!active) return;

            const supabase = getSupabaseBrowserClient();
            if (!supabase) {
                setConfigured(isSupabaseConfigured);
                setLoading(false);
                return;
            }

            // No `getSession()` first: a new subscriber is always handed the
            // restored session as INITIAL_SESSION (auth-js GoTrueClient,
            // `_emitInitialSession`, which fires with null if the restore
            // fails), so asking separately only commits the same session twice
            // on mount. That event is what clears `loading`.
            const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
                apply(session?.access_token ?? null, session?.user.email ?? null);
            });
            unsubscribe = () => listener.subscription.unsubscribe();
        })();

        return () => {
            active = false;
            unsubscribe();
        };
    }, [apply]);

    /* -------------------------------------------------------- sign in */

    const signInWithGoogle = useCallback(async (next?: string) => {
        const { getSupabaseBrowserClient } = await import("@/lib/supabase/client");
        const supabase = getSupabaseBrowserClient();
        if (!supabase) return { error: "Supabase sign-in is not configured in this environment." };

        const callback = new URL("/auth/callback", window.location.origin);
        if (next) callback.searchParams.set("next", next);

        const { error } = await supabase.auth.signInWithOAuth({
            provider: "google",
            options: {
                redirectTo: callback.toString(),
                // hd narrows Google's account chooser to CDTM addresses. It is
                // a convenience, not a control: the backend is what rejects a
                // non-cdtm.com account.
                queryParams: { hd: "cdtm.com", prompt: "select_account" },
            },
        });
        return { error: error?.message ?? null };
    }, []);

    const signInAsDev = useCallback(
        async (address: string, memberSlug?: string | null) => {
            // The call and its error handling both live in `api/`: the path is
            // declared once against the generated schema, and the envelope is
            // read by the same code every other request uses.
            let login: DevLoginResponse;
            try {
                login = await devLogin(address, memberSlug ?? null);
            } catch (error) {
                return { error: errorMessage(error) };
            }
            const stored = await fetch("/api/auth/dev-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: login.access_token,
                    expires_in: login.expires_in,
                    email: address,
                }),
            });
            if (!stored.ok) return { error: "Could not store the session cookie." };

            apply(login.access_token, address);
            router.refresh();
            return { error: null };
        },
        [apply, router],
    );

    /* ------------------------------------------------------- sign out */

    const signOut = useCallback(async () => {
        if (isDevAuth) {
            await fetch("/api/auth/dev-session", { method: "DELETE" });
        } else {
            const { getSupabaseBrowserClient } = await import("@/lib/supabase/client");
            await getSupabaseBrowserClient()?.auth.signOut();
        }
        apply(null, null);
        router.refresh();
    }, [apply, router]);

    // No `token` here: a refresh must not re-render everything that only asked
    // whether there is a session (see TokenContext above).
    const value = useMemo<AuthState>(
        () => ({
            mode: AUTH_MODE,
            email,
            signedIn,
            loading,
            configured,
            signInWithGoogle,
            signInAsDev,
            signOut,
        }),
        [email, signedIn, loading, configured, signInWithGoogle, signInAsDev, signOut],
    );

    return (
        <AuthContext.Provider value={value}>
            <TokenContext.Provider value={token}>{children}</TokenContext.Provider>
        </AuthContext.Provider>
    );
}

export function useSession(): AuthState {
    const value = useContext(AuthContext);
    if (!value) throw new Error("useSession must be used inside <AuthProvider>");
    return value;
}

/**
 * The current access token, for the one thing that sends a request outside the
 * typed API client (the media upload, which is an XHR for its progress events).
 * Null while the session is being restored, exactly as before.
 */
export function useAccessToken(): string | null {
    return useContext(TokenContext);
}
