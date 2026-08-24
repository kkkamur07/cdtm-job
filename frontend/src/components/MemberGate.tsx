import Link from "next/link";

import { loadMe } from "@/api/server";
import { ApiError } from "@/api/errors";
import { getIdentity } from "@/auth/session";
import { isDevAuth } from "@/auth/mode";

/**
 * Wraps everything the community side of the app can only show to a signed-in
 * CDTM member. There are four states worth telling apart, and each one has a
 * different thing for the visitor to do next:
 *
 *   not signed in         go to /login
 *   wrong account         the backend rejected the domain (403 at /auth/me)
 *   signed in, unlinked   the account exists but no member row is bound to it
 *   ready                 render the page
 *
 * `requireMember` is false for screens that only need a session (reading the
 * directory), true for anything that writes.
 *
 * This runs on the server, so a signed-out visitor is never sent the page's
 * JavaScript at all.
 */
export default async function MemberGate({
    children,
    requireMember = false,
    next,
}: {
    children: React.ReactNode;
    requireMember?: boolean;
    /** Where to return to after signing in. */
    next?: string;
}) {
    const { accessToken } = await getIdentity();

    if (!accessToken) {
        return (
            <Notice title="Sign in to see the community">
                <p className="mb-4">
                    The directory, events, housing and intros are for CDTM members. Jobs and
                    companies stay open to everyone.
                </p>
                <Link
                    href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}
                    className="btn btn-blue"
                >
                    {isDevAuth ? "Sign in" : "Sign in with CDTM Google"}
                </Link>
            </Notice>
        );
    }

    let me;
    try {
        me = await loadMe();
    } catch (error) {
        if (error instanceof ApiError && error.isForbidden) {
            return (
                <Notice title="That account cannot be used here">
                    <p className="mb-4">{error.message}</p>
                    <p>
                        Sign in again with your <b>@cdtm.com</b> address.
                    </p>
                </Notice>
            );
        }
        if (error instanceof ApiError && error.isAuth) {
            return (
                <Notice title="Your session has expired">
                    <p className="mb-4">Sign in again to pick up where you left off.</p>
                    <Link href="/login" className="btn btn-blue">
                        Sign in
                    </Link>
                </Notice>
            );
        }
        return (
            <Notice title="That did not load">
                <p>
                    {error instanceof ApiError
                        ? error.message
                        : "The API did not answer. Check that the backend is running."}
                </p>
            </Notice>
        );
    }

    if (requireMember && !me.member_id) {
        return (
            <Notice title="Create your profile first">
                <p className="mb-4">
                    You are signed in as <b>{me.account.email}</b>, but no one in the CDTM roster
                    matched that address yet. Create your directory profile and you can post, save
                    and be found like everyone else.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                    <Link href={next ? `/onboarding?next=${encodeURIComponent(next)}` : "/onboarding"} className="btn btn-blue">
                        Create your profile
                    </Link>
                    <Link href="/network" className="btn">
                        Browse the network
                    </Link>
                </div>
            </Notice>
        );
    }

    return <>{children}</>;
}

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="shell py-12">
            <div className="card mx-auto max-w-[34rem] p-6 text-[13.5px] leading-relaxed">
                <h1 className="mb-2 text-lg font-semibold">{title}</h1>
                <div className="text-muted [&_b]:text-ink">{children}</div>
            </div>
        </div>
    );
}
