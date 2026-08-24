/**
 * Where a `?next=` parameter is allowed to send somebody.
 *
 * The sign-in screen and the OAuth callback both take a return address from
 * the query string, and both are a phishing tool if they will bounce to
 * another origin on the strength of it. One rule, in one place: a path on this
 * app, or the home page. `//evil.example` is rejected too, because a browser
 * reads a protocol-relative URL as another origin.
 */
export function safeNext(value: string | null | undefined): string {
    if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
    return value;
}
