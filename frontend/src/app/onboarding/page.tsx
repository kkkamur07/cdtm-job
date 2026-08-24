import { redirect } from "next/navigation";

import { getIdentity } from "@/auth/session";
import OnboardingForm from "./OnboardingForm";

export const metadata = { title: "Create your profile · CDTM Community" };

/**
 * Where a signed-in account with no roster match lands to claim a member
 * profile for itself. Signed-out visitors are sent to sign in first and back
 * here after; the form itself refuses (client-side) to run for an account that
 * is already linked.
 */
export default async function OnboardingPage() {
    const { accessToken } = await getIdentity();
    if (!accessToken) redirect("/login?next=/onboarding");

    return (
        <main id="main" className="grid min-h-screen place-items-center px-4 py-10">
            <OnboardingForm />
        </main>
    );
}
