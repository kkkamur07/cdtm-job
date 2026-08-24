import type { Metadata, Viewport } from "next";

import "./globals.css";
import Providers from "./providers";
import { getIdentity } from "@/auth/session";

const DESCRIPTION =
    "The CDTM network: people, paths, jobs, housing, events and announcements in one place.";

/**
 * The site is behind a sign-in, so an unfurled link shows the shell, never a
 * member's page. `openGraph` exists to make that card readable, not to leak
 * anything: no member name, photo or listing detail goes in it, and the whole
 * app is marked noindex for the same reason.
 *
 * Every page spells out its own full title, so there is no `title.template`
 * here; one would double the suffix.
 */
export const metadata: Metadata = {
    metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
    title: "CDTM Community",
    description: DESCRIPTION,
    applicationName: "CDTM Community",
    openGraph: {
        type: "website",
        siteName: "CDTM Community",
        title: "CDTM Community",
        description: DESCRIPTION,
        locale: "en_GB",
    },
    twitter: {
        card: "summary",
        title: "CDTM Community",
        description: DESCRIPTION,
    },
    robots: { index: false, follow: false },
};

/** Matches the page background, so the browser chrome does not band against it. */
export const viewport: Viewport = {
    themeColor: "#f6f6f4",
    colorScheme: "light",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
    // Passed down so the first client paint already knows whether somebody is
    // signed in, rather than flashing the signed-out header.
    const { email, accessToken } = await getIdentity();

    return (
        <html lang="en">
            <body>
                <a
                    href="#main"
                    className="sr-only rounded-full bg-blue px-4 py-2 text-white focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50"
                >
                    Skip to content
                </a>
                <Providers initialEmail={email} initialSignedIn={Boolean(accessToken)}>
                    {children}
                </Providers>
            </body>
        </html>
    );
}
