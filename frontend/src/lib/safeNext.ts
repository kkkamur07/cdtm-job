/**
 * Where a `?next=` parameter is allowed to send somebody.
 *
 * The sign-in screen and the OAuth callback both take a return address from
 * the query string, and both are a phishing tool if they will bounce to
 * another origin on the strength of it. One rule, in one place: a path on this
 * app, or the home page.
 *
 * String tests alone are not enough. `//evil.example` is a protocol-relative
 * URL, and `/\evil.example` is one too as far as every browser's URL parser is
 * concerned, so the value is parsed against a throwaway base and kept only if
 * it stayed on that base. What comes back is rebuilt from the parsed URL, so
 * whatever the caller is handed is what the parser saw.
 */
export function safeNext(value: string | null | undefined): string {
    if (!value || !value.startsWith("/")) return "/";
    // Both of the two-character openings a browser reads as an authority.
    if (value.startsWith("//") || value.startsWith("/\\")) return "/";

    const base = "http://n";
    let url: URL;
    try {
        url = new URL(value, base);
    } catch {
        return "/";
    }
    return url.origin === base ? url.pathname + url.search + url.hash : "/";
}
