export function PostJobSidebar() {
  return (
    <aside className="space-y-4 lg:sticky lg:top-20">
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="text-section-label">Before you publish</h2>
        <ul className="mt-4 space-y-3 text-sm leading-relaxed text-zinc-600">
          <li className="flex gap-2">
            <span className="text-cdtm" aria-hidden>
              ·
            </span>
            <span>Use a clear title candidates would search for.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-cdtm" aria-hidden>
              ·
            </span>
            <span>
              Add an application URL or email so interested people know how to reach you.
            </span>
          </li>
          <li className="flex gap-2">
            <span className="text-cdtm" aria-hidden>
              ·
            </span>
            <span>New companies need a unique URL slug. We suggest one from the name.</span>
          </li>
        </ul>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-zinc-50/60 p-5">
        <p className="text-xs leading-relaxed text-zinc-500">
          Listings are public immediately. In production, gate this flow behind authentication
          or an API key.
        </p>
      </div>
    </aside>
  );
}
