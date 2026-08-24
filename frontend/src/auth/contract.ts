import type { components } from "@/api/schema";

/**
 * The dev sign-in shapes, taken from the generated schema rather than restated
 * here, so a change on the backend shows up as a compile error.
 *
 *   GET  /api/v1/auth/dev/members?q=   -> DevMemberOption[]   (unauthenticated)
 *   POST /api/v1/auth/dev/login        -> DevLoginResponse
 */
export type DevMember = components["schemas"]["DevMemberOption"];
export type DevLoginRequest = components["schemas"]["DevLoginRequest"];
export type DevLoginResponse = components["schemas"]["DevLoginResponse"];

/**
 * What the browser learns about its own session from /api/auth/dev-session.
 * This one is ours: the token lives in an httpOnly cookie, and this is the
 * slice of it a client component is allowed to see.
 */
export type DevSession = {
    accessToken: string;
    email: string | null;
    expiresAt: number | null;
};
