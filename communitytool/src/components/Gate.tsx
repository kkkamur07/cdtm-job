"use client";

import { Suspense, useEffect, useState } from "react";
import { hasSession } from "@/lib/auth";
import LoginScreen from "./LoginScreen";
import Directory from "./Directory";

/**
 * Chooses between the login screen and the directory.
 *
 * `ready` exists because sessionStorage is unavailable during the server pass
 * and the first client render. Rendering the login screen before that check
 * would flash it at users who are already signed in.
 */
export default function Gate({ header }: { header: React.ReactNode }) {
  const [unlocked, setUnlocked] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUnlocked(hasSession());
    setReady(true);
  }, []);

  if (!ready) return null;

  if (!unlocked) return <LoginScreen onUnlock={() => setUnlocked(true)} />;

  return (
    <main>
      {header}
      <Suspense fallback={null}>
        <Directory />
      </Suspense>
    </main>
  );
}
