import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { DEV_SESSION_COOKIE } from "@/auth/mode";

/**
 * The dev session cookie.
 *
 * The token is minted by the backend (POST /api/v1/auth/dev/login). This route
 * parks it in an httpOnly cookie, which is what lets server components, route
 * handlers and the proxy read the session the same way they read a Supabase
 * one.
 *
 * The honest part: GET hands that same token back to JavaScript, and both POST
 * and GET return it in the response body. So the cookie being httpOnly does not
 * buy what httpOnly usually buys. Any script running on this origin can call
 * GET and walk away with a bearer token, which is exactly what an XSS payload
 * would do. The flag stops a stray `document.cookie` read; it does not stop
 * anything that can make a fetch.
 *
 * It is here because client components call the API directly and have to put
 * the token in an Authorization header, and this is dev-mode sign-in: it exists
 * so the app runs against a local backend with no identity provider, and it is
 * never the path in production (see `auth/mode.ts`, which forces Supabase
 * there).
 *
 * What it would take to close it properly: route every browser API call through
 * a handler on this origin that reads the cookie server-side and forwards the
 * request with the header attached, then delete GET and stop returning the
 * token from POST. That is a proxy for the whole `/api/v1` surface (streaming
 * and file upload included), plus `api/client.ts` pointed at the proxy instead
 * of the backend, plus the same treatment for the Supabase path so the two
 * modes do not diverge. It is a real piece of work, not a tweak, and it is not
 * being done under cover of a comment change.
 */

type Stored = { accessToken: string; email: string | null; expiresAt: number | null };

function encode(value: Stored): string {
    return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

export function decodeDevSession(raw: string | undefined): Stored | null {
    if (!raw) return null;
    try {
        const parsed = JSON.parse(Buffer.from(raw, "base64url").toString("utf8")) as Stored;
        if (typeof parsed.accessToken !== "string" || !parsed.accessToken) return null;
        if (parsed.expiresAt && parsed.expiresAt < Date.now()) return null;
        return parsed;
    } catch {
        return null;
    }
}

export async function GET() {
    const store = await cookies();
    const session = decodeDevSession(store.get(DEV_SESSION_COOKIE)?.value);
    return NextResponse.json(session, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
    const body = (await request.json().catch(() => null)) as {
        access_token?: string;
        expires_in?: number;
        email?: string | null;
    } | null;

    if (!body?.access_token) {
        return NextResponse.json({ error: "access_token is required" }, { status: 400 });
    }

    const maxAge = Math.max(60, Math.min(body.expires_in ?? 60 * 60 * 12, 60 * 60 * 24 * 30));
    const value: Stored = {
        accessToken: body.access_token,
        email: body.email ?? null,
        expiresAt: Date.now() + maxAge * 1000,
    };

    const store = await cookies();
    store.set(DEV_SESSION_COOKIE, encode(value), {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge,
    });

    return NextResponse.json(value, { headers: { "Cache-Control": "no-store" } });
}

export async function DELETE() {
    const store = await cookies();
    store.delete(DEV_SESSION_COOKIE);
    return new NextResponse(null, { status: 204 });
}
