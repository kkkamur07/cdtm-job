import { NextResponse, type NextRequest } from "next/server";

import { safeNext } from "@/lib/safeNext";
import { createSupabaseServerClient } from "@/lib/supabase/server";

/**
 * Where Google sends the browser back after consent.
 *
 * The PKCE flow returns a one-time code in the query string; exchanging it
 * server-side is what writes the session cookies the middleware then keeps
 * fresh. Doing this in the browser instead would leave the server unable to see
 * the session at all.
 */
export async function GET(request: NextRequest) {
    const { searchParams, origin } = new URL(request.url);
    const code = searchParams.get("code");
    const next = safeNext(searchParams.get("next"));
    const error = searchParams.get("error_description") ?? searchParams.get("error");

    if (error) {
        return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(error)}`);
    }

    if (!code) {
        return NextResponse.redirect(`${origin}/login?error=missing_code`);
    }

    const supabase = await createSupabaseServerClient();
    if (!supabase) {
        return NextResponse.redirect(`${origin}/login?error=not_configured`);
    }

    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
    if (exchangeError) {
        return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(exchangeError.message)}`);
    }

    return NextResponse.redirect(`${origin}${next}`);
}
