import { Suspense } from "react";

import LoginForm from "./LoginForm";

export const metadata = { title: "Sign in · CDTM Community" };

export default function LoginPage() {
    return (
        <main id="main" className="grid min-h-screen place-items-center px-4 py-10">
            <Suspense fallback={null}>
                <LoginForm />
            </Suspense>
        </main>
    );
}
