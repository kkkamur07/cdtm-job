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
         * Every path except static assets and image files. Those never carry a
         * session and running the refresh on them would add a Supabase round
         * trip to each one.
         */
        "/((?!_next/static|_next/image|favicon.ico|assets|avatars|profiles|.*\\.(?:svg|png|jpg|jpeg|gif|webp|mp4)$).*)",
    ],
};
