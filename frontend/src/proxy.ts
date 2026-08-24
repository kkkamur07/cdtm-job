import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/proxy";

/**
 * Next.js 16 renamed `middleware.ts` to `proxy.ts`. All this does is keep the
 * Supabase session fresh; see lib/supabase/proxy.
 */
export async function proxy(request: NextRequest) {
    return updateSession(request);
}

export const config = {
    matcher: [
        /*
         * Documents only. Everything listed here either cannot carry a session
         * cookie back to the browser or has no use for one, and running the
         * refresh on it would add a Supabase round trip to each request:
         * static assets and images, the RSC data payloads under `_next/data`,
         * the route handlers under `api/` (the dev-session route is pure
         * cookie I/O and the rest of the API lives on the backend), and the
         * metadata files a crawler asks for.
         *
         * A router prefetch is not excluded and must not be: it asks for the
         * document's own path with an RSC header, so it matches here and gets
         * the refresh, which is the only way its rotated cookies survive.
         */
        "/((?!api/|_next/static|_next/image|_next/data|favicon.ico|robots.txt|sitemap.xml|manifest|assets|avatars|profiles|.*\\.(?:svg|png|jpg|jpeg|gif|webp|mp4|ico|txt|xml|json|woff2?)$).*)",
    ],
};
