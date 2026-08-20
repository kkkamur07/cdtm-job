"use client";

import { useState } from "react";
import { rememberSession, verifyPassword } from "@/lib/auth";

/**
 * Sign-in screen. Google is a placeholder for the real SSO flow; the password
 * field is the temporary way in.
 *
 * Deliberately plain — one card, one action, no marketing. The blue panel is
 * the only saturated surface on the page.
 */
export default function LoginScreen({ onUnlock }: { onUnlock: () => void }) {
  const [password, setPassword] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (checking || !password) return;

    setChecking(true);
    setError(null);

    // 600k PBKDF2 iterations take a beat; the button says so rather than
    // leaving the form looking inert.
    const ok = await verifyPassword(password);

    if (ok) {
      rememberSession();
      onUnlock();
      return;
    }

    setChecking(false);
    setPassword("");
    setError("That password isn't right.");
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-[26rem]">
        <div className="mb-7 flex items-center justify-center">
          <img src="/assets/cdtm.svg" alt="CDTM Logo" width={36} height={36} className="h-9 w-auto" />
          <div className="ml-3 flex items-center">
            <div className="mr-2 h-6 w-px bg-black" />
            <span className="text-lg font-semibold" style={{ color: "#134391" }}>
              Community
            </span>
          </div>
        </div>

        <div className="rounded-3xl border border-transparent bg-[color:var(--cdtm-blue)] p-5 text-white">
          <h1 className="px-1 pt-1 text-lg font-semibold tracking-tight">Good to see you!</h1>
          <p className="mt-1 px-1 text-[13px] leading-relaxed text-white/70">
              Sign in to access the internal CDTM community platform
          </p>

          <button
            type="button"
            disabled
            title="Google sign-in is not connected yet"
            className="mt-5 flex h-11 w-full cursor-not-allowed items-center justify-center gap-2.5 rounded-[var(--radius-pill)] bg-white/95 text-sm font-medium text-ink opacity-60"
          >
            <GoogleMark />
            Continue with Google
          </button>
          <p className="mt-1.5 text-center text-[11px] text-white/50">Coming soon</p>

          <div className="my-5 flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1 bg-white/20" />
            <span className="text-[11px] tracking-wider text-white/50 uppercase">or</span>
            <span className="h-px flex-1 bg-white/20" />
          </div>

          <form onSubmit={submit} noValidate>
            <label htmlFor="password" className="px-1 text-[13px] font-medium text-white/80">
              Access password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (error) setError(null);
              }}
              autoComplete="current-password"
              autoFocus
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "password-error" : undefined}
              className="mt-1.5 h-11 w-full rounded-[var(--radius-pill)] border border-white/25 bg-white/10 px-4 text-sm text-white transition-colors placeholder:text-white/40 focus:border-white/60 focus:outline-none"
              placeholder="Enter password"
            />

            {/* Reserved height, so an error doesn't shift the button. */}
            <p
              id="password-error"
              role="alert"
              className="mt-1.5 min-h-4 px-1 text-[12px] text-white/80"
            >
              {error ?? "\u00A0"}
            </p>

            <button
              type="submit"
              disabled={checking || !password}
              className="mt-1.5 h-11 w-full rounded-[var(--radius-pill)] bg-[color:var(--cdtm-green)] text-sm font-semibold text-ink transition-opacity disabled:opacity-45"
            >
              {checking ? "Checking…" : "Continue"}
            </button>
          </form>
        </div>

      </div>
    </main>
  );
}

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}
