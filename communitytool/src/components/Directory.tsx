"use client";

import { useEffect, useState } from "react";
import type { MemberIndex } from "@/lib/types";
import MemberGrid from "./MemberGrid";

/**
 * Fetches the member index at runtime rather than importing it.
 *
 * A static import would inline ~1MB of names into the JS bundle, which the
 * browser downloads before the login screen even renders. Fetching keeps the
 * directory out of the initial payload and defers it until after sign-in.
 *
 * To be clear about what this does NOT do: /data/index.json is still a public file
 * on the CDN. This is about payload and sequencing, not access control.
 */
export default function Directory() {
  const [data, setData] = useState<MemberIndex | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/data/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((json: MemberIndex) => !cancelled && setData(json))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <p className="shell py-24 text-center text-sm text-muted">
        The directory didn&rsquo;t load. Refresh to try again.
      </p>
    );
  }

  if (!data) {
    return (
      <div className="shell py-24 text-center" aria-busy="true">
        <p className="text-sm text-muted">Loading directory…</p>
      </div>
    );
  }

  return <MemberGrid members={data.members} classes={data.classes} />;
}
