"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { errorMessage } from "@/api/errors";
import { useDevMembers } from "@/api/hooks/auth";
import { useSession } from "@/auth/AuthProvider";
import { isDevAuth } from "@/auth/mode";
import type { DevMember } from "@/auth/contract";
import { safeNext } from "@/lib/safeNext";
import { useDebounced } from "@/lib/useDebounced";

/**
 * Two ways in, one screen.
 *
 * Dev mode trades a CDTM address for a token so the app can be run against a
 * local backend with no identity provider at all. Supabase mode is the real
 * one: Google, restricted to cdtm.com. Which is active is a build-time
 * decision, so only one of them is ever drawn.
 */
export default function LoginForm() {
    const router = useRouter();
    const params = useSearchParams();
    const next = safeNext(params.get("next"));
    const { signedIn, signInAsDev, signInWithGoogle, configured } = useSession();

    const [email, setEmail] = useState("");
    const [member, setMember] = useState<DevMember | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (signedIn) router.replace(next);
    }, [signedIn, next, router]);

    const submit = async (event: React.FormEvent) => {
        event.preventDefault();
        setError(null);

        if (!email.trim().toLowerCase().endsWith("@cdtm.com")) {
            setError("Use your @cdtm.com address.");
            return;
        }

        setBusy(true);
        const result = await signInAsDev(email.trim(), member?.slug ?? null);
        setBusy(false);
        if (result.error) setError(result.error);
        else router.replace(next);
    };

    return (
        <div className="w-full max-w-[26rem]">
            <Link href="/" className="mb-6 flex w-fit items-center">
                <img src="/assets/cdtm.svg" alt="" width={32} height={32} className="h-8 w-auto" />
                <span className="mr-2 ml-3 h-5 w-px bg-ink" />
                <span className="text-[15px] font-semibold text-blue">Community</span>
            </Link>

            <div className="card p-6">
                <h1 className="text-lg font-semibold">Sign in</h1>

                {isDevAuth ? (
                    <>
                        <p className="mt-1.5 text-[13.5px] text-muted">
                            No identity provider is wired up in this environment, so the backend
                            issues the token directly. Any <b className="text-ink">@cdtm.com</b>{" "}
                            address works.
                        </p>

                        <form onSubmit={submit} className="mt-5 grid gap-4">
                            <div>
                                <label className="label" htmlFor="email">
                                    CDTM e-mail
                                </label>
                                <input
                                    id="email"
                                    className="input"
                                    type="email"
                                    autoComplete="email"
                                    required
                                    placeholder="you@cdtm.com"
                                    value={email}
                                    onChange={(event) => setEmail(event.target.value)}
                                />
                            </div>

                            {/* The picker hands back a slug, never an address:
                                /auth/dev/members is unauthenticated and
                                deliberately does not return e-mails. The slug
                                is what POST /auth/dev/login identifies the
                                member by, so nothing here has to fill the
                                e-mail field in. */}
                            <MemberPicker selected={member} onSelect={setMember} />

                            {error && (
                                <p role="alert" className="text-[13px] text-red-700">
                                    {error}
                                </p>
                            )}

                            <button type="submit" className="btn btn-blue w-full" disabled={busy}>
                                {busy ? "Signing in…" : "Sign in"}
                            </button>
                        </form>
                    </>
                ) : (
                    <>
                        <p className="mt-1.5 text-[13.5px] text-muted">
                            The community directory, events and housing are for CDTM members.
                        </p>
                        {!configured && (
                            <p className="mt-3 text-[13px] text-red-700">
                                Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and
                                NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, or run in dev auth mode.
                            </p>
                        )}
                        <button
                            type="button"
                            className="btn btn-blue mt-5 w-full"
                            disabled={busy || !configured}
                            onClick={async () => {
                                setBusy(true);
                                const result = await signInWithGoogle(next);
                                if (result.error) {
                                    setError(result.error);
                                    setBusy(false);
                                }
                            }}
                        >
                            {busy ? "Opening Google…" : "Continue with CDTM Google"}
                        </button>
                        {error && (
                            <p role="alert" className="mt-3 text-[13px] text-red-700">
                                {error}
                            </p>
                        )}
                    </>
                )}
            </div>

            <p className="mt-4 text-center text-[12.5px] text-muted">
                <Link href="/jobs" className="hover:text-ink">
                    Browse jobs without signing in
                </Link>
            </p>
        </div>
    );
}

/** Optional: sign in as a specific person from the roster. */
function MemberPicker({
    selected,
    onSelect,
}: {
    selected: DevMember | null;
    onSelect: (member: DevMember | null) => void;
}) {
    const [query, setQuery] = useState("");
    const debounced = useDebounced(query, 250);

    // The request, its cancellation and its caching all belong to the query
    // layer; this only says what it wants. The path itself lives in
    // `api/hooks/auth.ts` with every other endpoint.
    const members = useDevMembers(debounced);
    const shown: DevMember[] = debounced.trim() ? (members.data ?? []) : [];

    return (
        <div>
            <label className="label" htmlFor="member-search">
                Sign in as a roster member (optional)
            </label>
            <input
                id="member-search"
                className="input"
                type="search"
                placeholder="Search the roster by name"
                value={selected ? selected.name : query}
                onChange={(event) => {
                    onSelect(null);
                    setQuery(event.target.value);
                }}
                role="combobox"
                aria-expanded={shown.length > 0}
                aria-controls="member-results"
                autoComplete="off"
            />

            {members.error && (
                <p className="mt-1.5 text-[12px] text-muted">
                    {errorMessage(members.error)} Signing in by e-mail still works.
                </p>
            )}

            {!selected && shown.length > 0 && (
                <ul id="member-results" className="card mt-1.5 max-h-56 overflow-y-auto p-1">
                    {shown.slice(0, 8).map((item) => (
                        <li key={item.slug}>
                            <button
                                type="button"
                                className="w-full rounded-xl px-2.5 py-2 text-left text-[13px] hover:bg-cream"
                                onClick={() => {
                                    onSelect(item);
                                    setQuery("");
                                }}
                            >
                                <span className="font-medium">{item.name}</span>
                                {item.class_label && (
                                    <span className="ml-1.5 text-muted">{item.class_label}</span>
                                )}
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
