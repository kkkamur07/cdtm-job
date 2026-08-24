# FE server data-flow implementation

Implemented against the audit in `fe-waterfalls.md` and the Supabase section of
`supabase-auth.md`. Every finding was re-confirmed at its cited location before it was
changed. Verified with `npm run typecheck`, `npm run lint` and `npm run build` from
`frontend/` (all three clean at the end; the pre-existing `LoginForm.tsx:94` type error and
the two `MemberGrid.tsx` lint errors were fixed by the other agent while this work ran).

## 1. Remove `force-dynamic` from the three job-board routes: done

Rule: `server-cache-lru` (Data Cache) / the Next 16 `caching-without-cache-components` doc.

Confirmed at `jobs/page.tsx:16`, `jobs/[slug]/page.tsx:22`, `companies/page.tsx:11`. Removed
all three exports and rewrote the comments to say why the export was wrong rather than why it
was there: reading the request's cookies through `getAccessToken` already makes every one of
these routes dynamic, and `force-dynamic` additionally implies
`fetchCache = "force-no-store"`, which killed the `revalidate: 60` on `loadJobs`/`loadJobBySlug`
and the `revalidate: 300` on `loadCompanies`/`loadCompany` on exactly the routes those windows
were written for.

The build route table still shows `ƒ` (dynamic) for `/jobs`, `/jobs/[slug]` and `/companies`,
which is the expected outcome: nothing became statically prerendered, the Data Cache is simply
reachable again for signed-out traffic.

Files: `src/app/(app)/jobs/page.tsx`, `src/app/(app)/jobs/[slug]/page.tsx`,
`src/app/(app)/companies/page.tsx`.

## 2. Unread badge reads a count endpoint: done

Rule: `server-serialization`.

Confirmed at `(app)/layout.tsx:20` (`loadAnnouncements()` for `.unread` on every route).
Added `loadUnreadCount = cache(() => get<{ unread: number }>("/announcements/unread-count"))`
to `api/server.ts`, with the comment explaining why `limit: 1` would not have worked
(`React.cache` keys on the argument, so the shell and the announcements page would then make
two requests where they now make one). The layout's `Promise.all` now calls it in place of
`loadAnnouncements`, still with `.catch(() => null)` and `unread?.unread ?? 0`.

Caveats, both deliberate:

- The backend endpoint does not exist yet (`GET /api/v1/announcements/unread-count` is absent
  from `backend/announcements/api/` and from the committed `openapi.json`). Until the backend
  agent lands it, the layout's `.catch(() => null)` makes the badge read 0 rather than break
  the shell. Nothing else regresses.
- `loadAnnouncements` is kept for `/announcements` and the home feed, as instructed. One
  consequence: `/` now makes one request more than before (the count for the shell badge, plus
  the 50-item list for the feed panel, which used to be a single deduped call). That is a
  1-request regression on one route against a 50-row-payload saving on the other thirteen.

Files: `src/api/server.ts`, `src/app/(app)/layout.tsx`.

## 3. `/paths` hydration refetch and the container `content-visibility`: done

Rule: `client-swr-dedup` (`initialData` seeding), plus a CSS containment correction.

Confirmed at `api/hooks/community.ts:268` (no `initialData`) and `PathsExplorer.tsx:55`.
`usePathFlow(params, initialData?: PathFlow)` now follows the same shape as `useEvents` /
`useAnnouncements` in the same file, keeping its existing `placeholderData: (previous) =>
previous`. `PathsExplorer` passes `initialFlow` as `initialData` only when there is no class
filter, so the unfiltered flow the server already drew is not asked for again on hydration.
This is the heaviest endpoint on the site and it was being computed twice per page view.

Also removed `[content-visibility:auto]` from the two container `<ul>` elements (they were at
lines 175 and 206; a container rule with no `contain-intrinsic-size` only collapses the
element's height and breaks scroll anchoring). The per-row `.cv-row` classes are untouched.

Files: `src/api/hooks/community.ts`, `src/features/community/paths/PathsExplorer.tsx`.

## 4. MemberGate no longer costs a serial hop: done

Rule: `async-suspense-boundaries` (the shared-promise form), `server-parallel-fetching`.

Confirmed at `MemberGate.tsx:34-55`: the gate awaited `/auth/me` before React was allowed to
render `children`, so every gated page's own reads started a full round trip late.

Added one exported helper next to the gate:

```ts
export function gatedData<T>(load: () => Promise<T>): Promise<T | null> {
    const data = getIdentity().then(({ accessToken }) => (accessToken ? load() : null));
    data.catch(() => {});
    return data;
}
```

`getIdentity` is `React.cache`d, so the gate and the page share one identity resolution and
their reads go out together. The `data.catch(() => {})` is load-bearing: the gate can decide
not to render the child at all (expired session, wrong account), which would otherwise leave a
rejection unobserved and, on Node's default `--unhandled-rejections=throw`, take the process
with it. Whoever awaits the promise still sees the rejection.

Each page is now synchronous (or, where it has route params, awaits only `params`, which costs
no round trip) and hands the promise to an async child rendered inside `<MemberGate>`:

| Route | Loader | Child |
|---|---|---|
| `/` | `loadFeed` (both waves) | `<Feed data={…}>` |
| `/members/[slug]` | `loadProfile(slug)` | `<Profile data={…}>` |
| `/housing` | `loadBoard` | `<Listings data={…}>` |
| `/housing/[id]` | `loadListing(id)` | `<Listing data={…}>` |
| `/paths` | `loadPaths` | `<Paths data={…}>` |
| `/events` | inline `loadEvents(upcoming)` | `<Events events={…}>` |
| `/me` | `loadAccount` | `<Me data={…}>` |

`generateMetadata` dedup is unaffected: every loader is still `React.cache`d with primitive
arguments, and the members and housing detail pages still resolve their title from the same
cached read the body uses.

Files: `src/components/MemberGate.tsx`, `src/app/(app)/page.tsx`,
`src/app/(app)/members/[slug]/page.tsx`, `src/app/(app)/housing/page.tsx`,
`src/app/(app)/housing/[id]/page.tsx`, `src/app/(app)/paths/page.tsx`,
`src/app/(app)/events/page.tsx`, `src/app/(app)/me/page.tsx`.

## 5. Signed-out renders no longer fire authenticated calls: done

Rule: `async-cheap-condition-before-await`.

Three places, all confirmed against the measured production traces:

- **Gated pages** (`/`, `/members/[slug]`, `/housing`, `/housing/[id]`, `/paths`, `/events`,
  `/me`): `gatedData` checks `getIdentity()` and returns `null` without calling any loader when
  there is no token. The gate renders the sign-in notice, so the child never renders; the
  `if (!loaded) return null` branch in each child exists only to satisfy the type.
- **`/members/[slug]` and `/housing/[id]` `generateMetadata`**: both now return the generic
  title straight away when there is no token, instead of issuing a `members/{slug}` or
  `housing/{id}` request that can only 401.
- **`/jobs`**: `getIdentity()` joined the first `Promise.all` (it is cached and cheap), and the
  second wave: `members/lookup` and `members/at-company`, both members-only: is skipped
  entirely for an anonymous visitor. The rows render with empty poster / at-company maps, which
  is exactly what they already did when those two reads failed.
- **`/jobs/[slug]`**: the poster lookup and `PeopleAtCompany` each check `getIdentity()` inside
  their own Suspense boundary and render nothing when signed out. The job and the company stay
  public.

Files: `src/components/MemberGate.tsx`, `src/app/(app)/jobs/page.tsx`,
`src/app/(app)/jobs/[slug]/page.tsx`, `src/app/(app)/members/[slug]/page.tsx`,
`src/app/(app)/housing/[id]/page.tsx`.

## 6. `/me` paints from the server payload: done

Rule: `client-swr-dedup` / `server-serialization`.

Confirmed at `me/page.tsx:8` and `me/Client.tsx:48-49`. `useMe` and `useMyMember` each take an
optional `initialData` (a two-line diff each in `api/hooks/me.ts`; nothing else in that file
was touched, and the other agent's `useSavedIds` addition landed alongside it without
conflict). `me/page.tsx` loads `loadMe()` and `loadMyMember()`: both already in the render's
`React.cache`, from the gate and the shell respectively, so they cost nothing: and hands them
to `MeBody`, which now takes optional `me` / `member` props.

Both loads are `.catch(() => null)` and the props are optional, so `MeBody` degrades to its
previous behaviour rather than throwing if either read fails.

`EntryForm`'s `useMyEntry` and `IntentsForm`'s `useMyIntents` were left alone: those files are
outside the assigned set and the default tab's first fetch is a smaller win than the header.

Files: `src/app/(app)/me/page.tsx`, `src/app/(app)/me/Client.tsx` (3 precise edits),
`src/api/hooks/me.ts` (2 precise edits).

## 7. Home page serializes all 50 announcements: SKIPPED, with the reason

Rule: `server-serialization`.

The finding is real and still stands at `(app)/page.tsx:119`: `<AnnouncementList limit={2}
initial={announcements} />` puts all 50 announcements with their bodies into the RSC payload of
the home page to draw two of them.

Neither of the two offered options is both correct and inside the assigned file set:

- **Slicing on the server alone is not correct here.** `AnnouncementList` seeds the shared
  `qk.announcements` key, and `providers.tsx:25` sets `staleTime: 30_000`. Seeding that key
  with a 2-item page means a client-side navigation from `/` to `/announcements` within 30
  seconds renders two announcements and does *not* refetch: the announcements page's own
  `initialData` is ignored, because React Query only applies `initialData` to an empty cache
  entry. That is a visible wrong list, not a background refetch.
- **Anything that forces the refetch reintroduces the fetch it was meant to remove.**
  `initialDataUpdatedAt: 0` or `placeholderData` both leave the home page itself fetching the
  50-item list from the browser on mount, which is worse than serializing it.
- **The correct fix is the distinct query key**, which needs one prop on
  `src/features/community/announcements/AnnouncementList.tsx`. That file is outside the
  assigned set, and the other agent modified it during this session (they hoisted the
  `preview` regex and added `cv-note`), so editing it would have collided.

The patch, for whoever owns that file: give `AnnouncementList` a `scope?: string` prop, thread
it into `useAnnouncements(initial, scope)` so the key becomes `["announcements", scope]`, pass
`scope="home"` and `initial={{ ...announcements, items: announcements.items.slice(0, 2) }}`
from `(app)/page.tsx`. Note that `useMarkAnnouncementRead` mutates `qk.announcements`
directly, so it needs the same scope to keep the optimistic read-flip working on the home
widget.

## 8. Poster lookups in their own boundary; one company instead of a hundred: done

Rules: `async-suspense-boundaries`, `server-parallel-fetching`, `async-dependencies`.

Confirmed at `housing/[id]/page.tsx:59` and `jobs/[slug]/page.tsx:53`: in both files the
`await loadMemberIndex([...])` sat above the `return`, so the suspended sidebar panels below , 
which only need `listing.city` or the company name: started a round trip later than they
could.

- `housing/[id]`: the poster block became `<Suspense fallback={null}><PostedBy
  memberId={listing.member_id} /></Suspense>`, so the poster, `MembersInCity` and `AlsoInCity`
  all start as soon as the listing is back and race each other.
- `jobs/[slug]`: same treatment for the poster, and `loadCompanyMap()` (which pulled
  `companies?limit=100` to name one company) is replaced by the `async-dependencies` chained
  form:

  ```ts
  const jobPromise = loadJobByRef(slug).catch(…);
  const companyPromise = jobPromise.then((job) =>
      job?.company_id ? loadCompany(job.company_id).catch(() => null) : null,
  );
  const [job, company] = await Promise.all([jobPromise, companyPromise]);
  ```

  The company request now goes out the instant the job lands, in parallel with the poster
  boundary, and `loadCompany` carries `revalidate: 300`, which item 1 just made reachable
  again.

Note: `loadCompanyMap` in `src/api/server.ts:167` is now referenced by nothing. I left it in
place rather than delete it: dead-code removal is audit item 15, which was not assigned, and
the file is being edited concurrently. It is an unreferenced server-only export, so it costs
nothing at runtime, but it should go.

Files: `src/app/(app)/jobs/[slug]/page.tsx`, `src/app/(app)/housing/[id]/page.tsx`.

## 9. Resource hints: done, with a documented substitution for the Supabase chunk

Rule: `rendering-resource-hints`, `bundle-preload`.

`src/api/config.ts` holds nothing but two `process.env` reads and no `server-only` guard, so it
imports cleanly into the root layout; the same is true of `src/lib/supabase/env.ts`. The root
layout now calls `preconnect(API_BASE_URL)` unconditionally and `preconnect(SUPABASE_URL)`
behind `isSupabaseConfigured`, before the `await getIdentity()`, so the hints are emitted while
the HTML is still streaming.

For the Supabase browser chunk I chose the **module-evaluation import**, not
`preloadModule`/`preinitModule`. Turbopack does not expose a stable, author-time chunk URL for
`import("@/lib/supabase/client")`: the href those APIs need does not exist until the build
emits it, and hard-coding a hashed path would rot on the next build. So `AuthProvider.tsx`
starts the download at module evaluation instead:

```ts
if (!isDevAuth && typeof window !== "undefined") {
    void import("@/lib/supabase/client").catch(() => {});
    void import("@/lib/supabase/env").catch(() => {});
}
```

The `typeof window` guard is the pattern the `bundle-preload` rule prescribes and keeps the
module out of the server graph. The restore effect is unchanged: its own `import()` now
resolves from the module registry rather than waiting a chunk round trip, so `token` (and every
query gated on it) stops waiting on hydration plus a fetch.

Files: `src/app/layout.tsx`, `src/auth/AuthProvider.tsx`.

## 10. Proxy matcher and prefetch skip: done

Rule: the Supabase Next.js SSR guidance; `async-cheap-condition-before-await`.

Confirmed at `src/proxy.ts:20` (the old lookahead skipped only `_next/static`, `_next/image`,
`favicon.ico`, `assets`, `avatars`, `profiles` and image extensions) and
`src/lib/supabase/proxy.ts:19,48`.

The matcher now also skips `api/`, `_next/data`, `robots.txt`, `sitemap.xml`, `manifest*` and
the `.ico|.txt|.xml|.json|.woff2?` extensions. Verified against the live regex in Node:

```
RUNS  /   /jobs   /jobs/some-slug   /me   /login   /auth/callback
skip  /api/auth/dev-session   /api/v1/x   /_next/data/x.json   /_next/static/chunk.js
skip  /robots.txt   /sitemap.xml   /manifest.webmanifest   /favicon.ico
skip  /avatars/a.webp   /assets/cdtm.svg   /profiles/x.json   /fonts/a.woff2
```

`updateSession` now returns before `createServerClient` in two cases: when
`!isSupabaseAuth || !isSupabaseConfigured`, and when the request carries
`next-router-prefetch` or `purpose: prefetch`.

On `mode.ts` semantics, checked carefully: `resolve()` returns `"supabase"` unconditionally
when `NODE_ENV === "production"`, so gating on `isSupabaseAuth` can only ever skip a local
dev-auth build, never a deployed one. That is the intended effect: a dev-auth build keeps its
token in an httpOnly cookie the Supabase client never touches, so the refresh was pure waste
there.

One honest caveat on the prefetch skip. The audit's stated rationale ("a prefetch cannot
deliver Set-Cookie to the browser anyway") is not quite right: a `<Link>` prefetch is a
same-origin `fetch`, and its `Set-Cookie` *is* applied to the cookie jar. What the skip really
buys is not paying a Supabase verification per prefetch, and what it costs is that a prefetched
RSC payload generated while the access token is expired renders as signed-out. In practice the
browser-side Supabase client refreshes the cookie on its own 30-second timer and the next
document request refreshes it server-side, and Next's dynamic prefetch entries are short-lived,
so the exposure is small. Flagging it because it is a behaviour change, not just a saving.

Files: `src/proxy.ts`, `src/lib/supabase/proxy.ts`.

## 11. One session read in `getServerAuth`: done

Rule: `async-parallel` (redundant sequential work).

Confirmed at `lib/supabase/server.ts:69-75`. `getSession()` is now read once and up front, an
absent session returns the empty identity without any further call, and `getClaims` is given
the token directly (`supabase.auth.getClaims(session.access_token)`) instead of re-reading the
session internally. `accessToken` is now `session.access_token` rather than an optional chain,
since the null case has already returned. The comment was updated to say that the session is
read once and why.

Files: `src/lib/supabase/server.ts`.

## 12. Delete `src/app/next.config.ts`: done

Deleted. It declared `output: "export"`, which the real `frontend/next.config.ts` explicitly
documents as gone, and Next never read it.

## 13. `React.cache` keyed by object identity: left as-is, honoured for new code

Rule: `server-cache-react`.

No active duplicate found, matching the audit, so the existing object-keyed loaders were left
alone. The one loader added in this work, `loadUnreadCount`, takes no arguments at all. The
`gatedData` helper takes a thunk rather than a key, so it introduces no new cache surface, and
`loadCompany(job.company_id)` in item 8 is keyed by a primitive id.

---

## Verification

```
npm run typecheck   clean
npm run lint        clean (0 problems)
npm run build       succeeds; 25 routes, all ƒ except the static /icon.svg
```

The two pre-existing `MemberGrid.tsx` lint errors and the `OnboardingForm.tsx` warning were
resolved by the other agent during the session, as was the `LoginForm.tsx:94` type error. No
new lint or type problems were introduced by this work.

Concurrent-edit note: the other agent modified `src/api/hooks/me.ts` (added `useSavedIds`),
`src/api/keys.ts` (split the housing key branches), `src/features/jobboard/JobsBrowser.tsx` and
`src/features/community/announcements/AnnouncementList.tsx` while this ran. All edits here were
precise string replacements, nothing was rewritten wholesale, and nothing of theirs was
reverted. At one point `npm run typecheck` failed on a half-saved `JobsBrowser.tsx`; that
cleared on its own and is not related to anything in this change set.
