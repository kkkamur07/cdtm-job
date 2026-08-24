import type { NextConfig } from "next";

/**
 * Images come from four places: the ingest output under `public/` (already
 * resized to 160px and 400px WebP by scripts/ingest.mjs), the API's media
 * endpoint, which serves uploaded job and housing images from a private bucket,
 * company logos that whoever created the company pasted in, and the picsum
 * placeholders the development seed uses for housing photos. Everything except
 * the first needs a remote pattern.
 */
const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");
const isProduction = process.env.NODE_ENV === "production";

/** Only the picsum placeholders are development-only; the rest ship everywhere. */
const remotePatterns: NonNullable<NonNullable<NextConfig["images"]>["remotePatterns"]> = [
    {
        protocol: apiUrl.protocol.replace(":", "") as "http" | "https",
        hostname: apiUrl.hostname,
        port: apiUrl.port,
        pathname: "/api/v1/media/**",
    },
    // Company logos. Clearbit is what the seed and the company form suggest; a
    // logo from anywhere else falls back to initials.
    { protocol: "https", hostname: "logo.clearbit.com" },
    // Google account avatars, for members who created their profile through
    // Google sign-in (the photo comes straight from the OAuth account). Served
    // from lh3..lh6.googleusercontent.com.
    { protocol: "https", hostname: "**.googleusercontent.com" },
];

// Member avatars live in a public Supabase Storage bucket once storage is
// switched on. Only the public object path is allowed; private buckets are
// never addressed from the browser (the API signs those).
if (process.env.NEXT_PUBLIC_SUPABASE_URL) {
    const supabase = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL);
    remotePatterns.push({
        protocol: "https",
        hostname: supabase.hostname,
        pathname: "/storage/v1/object/public/**",
    });
}

if (!isProduction) {
    // Development seed only: housing photo placeholders. A production build has
    // no business fetching images from a random placeholder host, so the
    // pattern is not compiled into it.
    remotePatterns.push(
        { protocol: "https", hostname: "picsum.photos" },
        { protocol: "https", hostname: "fastly.picsum.photos" },
    );
}

/**
 * Where the browser is allowed to fetch from. The API is a separate origin
 * (FastAPI on another port, or another host in a deployment), and Supabase is
 * a third one when that mode is switched on.
 */
const connectSources = ["'self'", apiUrl.origin];
if (process.env.NEXT_PUBLIC_SUPABASE_URL) connectSources.push(process.env.NEXT_PUBLIC_SUPABASE_URL);
if (!isProduction) connectSources.push("ws:", "http://localhost:*");

const imageSources = [
    "'self'",
    "data:",
    "blob:",
    apiUrl.origin,
    "https://logo.clearbit.com",
    // Google account avatars (lh3..lh6.googleusercontent.com) for Google-created profiles.
    "https://*.googleusercontent.com",
];
if (process.env.NEXT_PUBLIC_SUPABASE_URL) imageSources.push(process.env.NEXT_PUBLIC_SUPABASE_URL);
if (!isProduction) imageSources.push("https://picsum.photos", "https://fastly.picsum.photos");

/**
 * The Content Security Policy.
 *
 * What is loosened, and why: `script-src` and `style-src` both carry
 * `'unsafe-inline'`. The App Router streams its RSC payload through inline
 * `self.__next_f.push(...)` bootstrap scripts and injects its own inline
 * `<style>` blocks, and this app draws inline `style` attributes (the chart
 * legend swatches, the staggered skeleton delays), which `style-src` also
 * governs. The only way to keep those and drop `'unsafe-inline'` is a
 * per-request nonce, and a nonce cannot be expressed in a static
 * `next.config.ts` header: it would have to move into `src/proxy.ts`, force
 * every route to render dynamically, and still fail in `next dev`, where
 * Turbopack injects HMR styles it does not nonce. Everything else is as tight
 * as the app allows: no `default-src` beyond `'self'`, no plugins, no framing,
 * and a fixed list of hosts the browser may reach.
 */
const csp = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src ${imageSources.join(" ")}`,
    "font-src 'self' data:",
    `connect-src ${connectSources.join(" ")}`,
    "media-src 'self'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-src 'none'",
    "frame-ancestors 'none'",
    ...(isProduction ? ["upgrade-insecure-requests"] : []),
].join("; ");

const nextConfig: NextConfig = {
    // The app talks to the FastAPI backend at runtime and holds a session in
    // the browser, so it is a normal Next server build. The static
    // `output: "export"` of the directory-only era is gone.
    images: { remotePatterns },

    /**
     * Security headers on every response.
     *
     * `frame-ancestors 'none'` in the CSP is what modern browsers obey;
     * `X-Frame-Options` is kept for the ones that do not. `Permissions-Policy`
     * turns off the device APIs this app never asks for, so a compromised
     * dependency cannot quietly reach the camera or the location.
     */
    async headers() {
        return [
            {
                source: "/:path*",
                headers: [
                    { key: "Content-Security-Policy", value: csp },
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    {
                        key: "Permissions-Policy",
                        value: [
                            "accelerometer=()",
                            "autoplay=()",
                            "camera=()",
                            "display-capture=()",
                            "encrypted-media=()",
                            "fullscreen=(self)",
                            "geolocation=()",
                            "gyroscope=()",
                            "magnetometer=()",
                            "microphone=()",
                            "midi=()",
                            "payment=()",
                            "usb=()",
                            "xr-spatial-tracking=()",
                        ].join(", "),
                    },
                ],
            },
        ];
    },

    // Pin the workspace root so a lockfile in a parent directory cannot make
    // Turbopack infer the wrong one.
    turbopack: { root: __dirname },

    // AGENTS.md in this directory is ours: it carries the project's rules,
    // including the house rule against em dashes. Next rewrites that file on
    // every `next dev` start and reintroduces them, so switch the generator off.
    agentRules: false,
};

export default nextConfig;
