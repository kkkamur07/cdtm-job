import createClient, { type Middleware } from "openapi-fetch";

import { API_BASE_URL } from "./config";
import { toApiError } from "./errors";
import type { paths } from "./schema";

/**
 * One typed client for the whole app, generated against the committed
 * openapi.json. Requests are made from the browser with the signed-in Account's
 * Supabase access token, so there is no server-side proxy and no secret here.
 */

/**
 * The current access token, read at request time rather than captured, so a
 * refresh reaches code that is already in flight.
 *
 * It is module state because it has to be readable before any component has
 * rendered: a query gated on the session fires from a child's effect, and a
 * child's effects run before its parent's, so a token published from the
 * provider's effect would arrive one tick after the first request went out.
 * AuthProvider sets it in the same callback that sets the session state, and
 * nothing else may call the setter. Only the browser bundle uses this client,
 * so there is no request-to-request leak on the server.
 */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
    accessToken = token;
}

const auth: Middleware = {
    async onRequest({ request }) {
        if (accessToken) request.headers.set("Authorization", `Bearer ${accessToken}`);
        return request;
    },
};

export const api = createClient<paths>({ baseUrl: API_BASE_URL });
api.use(auth);

/**
 * openapi-fetch returns `{ data, error }`; React Query wants a promise that
 * rejects. This adapter is what every hook goes through, so the error envelope
 * is parsed exactly once.
 */
export async function unwrap<T>(
    result: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
    const { data, error, response } = await result;
    if (error !== undefined || !response.ok) throw toApiError(response, error);
    return data as T;
}
