# Frontend data-fetching and SSR audit: `frontend/` (Next.js 16.3.1, React 19)

Audit against the Vercel react-best-practices rules with prefix `async-` and `server-`
(`/Users/krishuagarwal/.claude/skills/react-best-practices/rules/`). Read-only; nothing in the
repository was modified.

Two behaviours were verified against the Next.js docs shipped in `node_modules/next/dist/docs`
rather than assumed, because both are load-bearing for the findings below:

- `01-app/01-getting-started/06-fetching-data.md:458` - "By default, layouts and pages are
  rendered in parallel. So each segment starts fetching data as soon as possible." So
  `(app)/layout.tsx` does **not** block the page segment's fetches from starting. It only
  blocks the shell flush.
- `01-app/03-api-reference/04-functions/generate-metadata.md:112` - fetch memoization is shared
  "across `generateMetadata`, `generateStaticParams`, Layouts, Pages, and Server Components".
  So the `generateMetadata` dedup claims in this codebase are correct.

---

## Findings

| # | Severity | Rule id | Location (file:line) | Evidence | Impact | Recommended fix |
|---|----------|---------|----------------------|----------|--------|-----------------|
| 1 | **Critical** | `server-cache-lru` (Data Cache) | `src/app/(app)/jobs/page.tsx:16`, `src/app/(app)/jobs/[slug]/page.tsx:22`, `src/app/(app)/companies/page.tsx:11` | `export const dynamic = "force-dynamic";` with the comment "The revalidate windows on the individual fetches still govern the Data Cache, so runtime caching is unchanged." | The comment is wrong for this Next version. `node_modules/next/dist/docs/01-app/02-guides/caching-without-cache-components.md:97-99` says `force-dynamic` is "equivalent to: setting the option of every `fetch()` request in a layout or page to `{ cache: 'no-store', next: { revalidate: 0 } }`" **and** `fetchCache = 'force-no-store'`. So the `revalidate: 60` on `loadJobs`/`loadJobBySlug` (`src/api/server.ts:128-134`) and `revalidate: 300` on `loadCompanies`/`loadCompany` (`src/api/server.ts:147-152`) are dead on exactly the three routes they were written for. Every signed-out visit to `/jobs` costs 4 live backend round trips instead of 0, `/jobs/[slug]` 4 instead of ~2, `/companies` 2 instead of 0. At 50-150ms each that is roughly +200-600ms of avoidable server time per public page view, on the only pages a search engine or a cold visitor sees. | Delete the three `export const dynamic = "force-dynamic"` lines. They are redundant for their stated purpose: every loader calls `getAccessToken()` -> `getIdentity()` -> `cookies()` (`src/auth/session.ts:29`, `src/api/server.ts:52`), and reading `cookies()` already makes the segment dynamic, so Next will never build-time prerender these routes anyway. If you want to keep `force-dynamic` as a guard, pair it with an explicit `export const fetchCache = "default-cache"`, which overrides the implied `force-no-store`. Verify with `next build` output and a second request timing. |
| 2 | **High** | `server-parallel-fetching`, `async-suspense-boundaries` | `src/components/MemberGate.tsx:34-55`, used by `src/app/(app)/page.tsx:32`, `members/[slug]/page.tsx:35`, `housing/page.tsx:12`, `housing/[id]/page.tsx:41`, `paths/page.tsx:9`, `events/page.tsx:20`, `events/[id]/page.tsx:32`, `me/page.tsx:8`, `post/page.tsx:29`, `network/page.tsx:11`, `announcements/page.tsx:10`, and the three `new/` composers | `const { accessToken } = await getIdentity(); ... me = await loadMe(); ... return <>{children}</>;` | The gate awaits `GET /auth/me` before React is allowed to render `children`, so every gated page's own fetches start one full backend round trip late. The layout is fetching `/auth/me` concurrently (`(app)/layout.tsx:17`) and `React.cache` dedups the HTTP call, so this costs no extra request, but it costs a serial hop: **+1 round trip (~50-150ms) on 15 of 18 app routes**, and it is the difference between the home feed's 8-way `Promise.all` starting at t=0 and starting at t=me. | Start the page's data before the gate awaits, using the shared-promise form from `async-suspense-boundaries`. e.g. in `(app)/page.tsx`: `export default function HomePage() { const data = feedData(); return <MemberGate next="/"><Feed data={data} /></MemberGate>; }` where `feedData()` is the un-awaited `Promise.all`. `HomePage` is synchronous, so the promises are created before `MemberGate` suspends. Applies verbatim to `members/[slug]`, `housing`, `housing/[id]`, `paths`, `events`. |
| 3 | **High** | `server-serialization` (over-fetch) | `src/app/(app)/layout.tsx:20` calling `src/api/server.ts:93-95` | `loadAnnouncements().catch(() => null)` -> `get(..."/announcements/", { limit: 50 })`, consumed as `unread={announcements?.unread ?? 0}` (`layout.tsx:29`) | Every single page render in the shell pulls 50 announcements with full `body` text over the wire, parses them, and reads one integer off the envelope. That is the layout's slowest of three fetches and it gates the shell flush (see #14). On a community with real announcement bodies this is tens of KB of JSON per page view, on every route. | Add a cheap `GET /api/v1/announcements/unread-count` on the backend and call that from the layout. Do not just drop the layout call to `limit: 1`: `React.cache` keys on the argument, so a `limit: 1` layout call and the `limit: 50` page call would become two HTTP requests on `/` and `/announcements` instead of one. A dedicated count endpoint is the only fix that is a win on all routes. |
| 4 | **High** | `client-swr-dedup`, `server-serialization` | `src/features/community/paths/PathsExplorer.tsx:55` vs `src/app/(app)/paths/page.tsx:18-22` | Server: `const [flow, groups, facets] = await Promise.all([loadPathFlow({}), ...])`. Client: `const flow = usePathFlow(classId ? { class_id: classId } : {});` with no `initialData` (`src/api/hooks/community.ts:268-276`). | `initialFlow` is passed down and used only as a render fallback (`shown = ... (flow.data ?? initialFlow)`), so on hydration the browser immediately refetches `GET /paths/flow` with the identical empty query. `paths/loading.tsx:5` itself says "The flow diagram is computed over every member, so this is the page most likely to be waited on" - and it is computed twice per page view, once on the server and once from the browser. **Doubles the cost of the heaviest endpoint on the site.** | Pass `initialFlow` through as `initialData` the way `useEvents`/`useAnnouncements` already do (`src/api/hooks/community.ts:31-39,138-146`): `usePathFlow(params, params is empty ? initialFlow : undefined)`. The pattern is already correct three files over; paths is the one that was missed. |
| 5 | **High** | `server-parallel-fetching`, `client-swr-dedup` | `src/app/(app)/me/page.tsx:6-13`, `src/app/(app)/me/Client.tsx:48-49` | Page is `<MemberGate requireMember next="/me"><MeBody /></MemberGate>`; `MeBody` then does `const me = useMe(); const member = useMyMember();` | The server already has both objects in hand: `MemberGate` awaited `/auth/me` and `(app)/layout.tsx:18-19` awaited `/auth/me` and `/members/me`. `/me` then throws that away and refetches both from the browser, and only after `AuthProvider` has finished restoring the session (`src/auth/AuthProvider.tsx:77-122`, an extra `/api/auth/dev-session` or `supabase.auth.getSession()` round trip first, because `useAuthedQueryOptions` gates on `!loading && signedIn`, `src/api/hooks/shared.ts:16`). Net: **the user's own page shows an empty header for 2-3 client round trips** after a fully-rendered HTML response that already contained the answer. | Fetch `loadMe()`/`loadMyMember()` in `me/page.tsx` and pass them into `MeBody` as `initialData` for `useMe`/`useMyMember` (add the optional `initialData` parameter the way `useEvent`/`useEvents` have it). Same for `EntryForm`'s `useMyEntry` and `IntentsForm`'s `useMyIntents` if you want the first tab to paint from HTML. |
| 6 | **Medium** | `server-serialization` | `src/app/(app)/page.tsx:119` | `<AnnouncementList limit={2} initial={announcements ?? undefined} />` | `AnnouncementList` is a `"use client"` component (`src/features/community/announcements/AnnouncementList.tsx:1`) and `announcements` is the full 50-item page from #3. All 50 items, bodies included, are serialized into the RSC payload / inline `__next_f` bootstrap on the home page, and `limit={2}` slices them in the browser. Directly the "serializes all 50 fields, uses 1" shape the rule names, times fifty rows. | Slice on the server: pass `initial={announcements ? { ...announcements, items: announcements.items.slice(0, 2) } : undefined}`. Note this changes what the React Query cache is seeded with, so either use a distinct query key for the home widget or accept a background refetch on `/announcements`. |
| 7 | **Medium** | `async-suspense-boundaries`, `server-parallel-fetching` | `src/app/(app)/housing/[id]/page.tsx:59` and `188-197` | `const members = await loadMemberIndex([listing.member_id]).catch(() => null);` sits above the `return`, and the two city panels are below it inside `<Suspense fallback={null}>` | `MembersInCity` and `AlsoInCity` only need `listing.city`, which is known the moment the listing arrives. Because the poster lookup is awaited before any JSX is returned, both suspended siblings start **one round trip later than they could**. Same shape at `src/app/(app)/jobs/[slug]/page.tsx:53`: `await loadMemberIndex([job.posted_by_member_id])` delays the `PeopleAtCompany` boundary at line 220-222, which only needs the company name. +1 serial round trip (~50-150ms) on the streamed sidebar of both detail pages. | Move the poster lookup into its own suspended child, e.g. `<Suspense fallback={null}><PostedBy memberId={listing.member_id} /></Suspense>`, so the three sidebar panels all start as soon as the listing/job is back and race each other instead of queueing. |
| 8 | **Medium** | `server-parallel-nested-fetching` | `src/app/(app)/jobs/[slug]/page.tsx:46` -> `src/api/server.ts:155-158` | `loadCompanyMap().catch(() => null)` -> `loadCompanies({ limit: 100 })` | The single-job page fetches **100 companies** to resolve one `company_id`. It is done that way to keep it parallel with the job fetch, which is a real trade-off and the comment at line 39-40 says so honestly. But `(app)/page.tsx:66-73` already demonstrates the better shape (`loadCompany(id)` per id, in the second wave), and one company by id after the job is almost certainly cheaper than 100 companies in parallel with it. | Chain it per `async-dependencies`: `const jobPromise = loadJobByRef(slug); const companyPromise = jobPromise.then(j => j.company_id ? loadCompany(j.company_id) : null); const [job, company] = await Promise.all([jobPromise, companyPromise]);`. Measure both before committing - if `/companies?limit=100` is served from the Data Cache once #1 is fixed, the current shape may win for signed-out visitors. |
| 9 | **Medium** | `async-suspense-boundaries` | `src/app/(app)/housing/page.tsx:19-25` | `const listings = await loadHousing(...); const members = await loadMemberIndex(listings.items.map(l => l.member_id))` | Genuinely dependent (the ids come off the listings), so this is not a `Promise.all` miss. But nothing renders until both are back, so the board pays 2 serial round trips before first paint. The listing cards are fully drawable without the byline. | Render `HousingBrowser` with `postedBy: null` immediately and stream the bylines in, or accept it and note that `housing/loading.tsx` at least keeps the shell up. Lower priority than #2, which removes a hop from the same route for free. |
| 10 | **Low** | `async-parallel` | `src/lib/supabase/server.ts:69-75` | `const { data } = await supabase.auth.getClaims(); ... const { data: { session } } = await supabase.auth.getSession();` | `getClaims()` with no argument internally calls `getSession()` first (`node_modules/@supabase/auth-js/dist/main/GoTrueClient.js:5322-5329`), so the session is read twice per render. Both reads are local cookie decodes in the normal case, so the cost is small - but it is free to remove. | `const { data: { session } } = await supabase.auth.getSession(); if (!session) return empty; const { data } = await supabase.auth.getClaims(session.access_token);` - one session read, and `getClaims` takes the token directly. |
| 11 | **Low** (conditional, but verify) | `async-parallel` | `src/lib/supabase/proxy.ts:48` and `src/lib/supabase/server.ts:69` | `await supabase.auth.getClaims()` in the proxy on every matched request, and again in `getServerAuth` on every render | `getClaims` verifies locally only when the token is asymmetric: `GoTrueClient.js:5341-5352` - `header.alg.startsWith('HS') ... ? null : await this.fetchJwk(...)`, and `if (!signingKey) { const { error } = await this.getUser(token) ... }`. On an **HS256** project (the legacy default, and what `backend/core/settings/auth.py:24` `SUPABASE_JWT_SECRET` supports) that is a network call to `/auth/v1/user`, **twice per page view**: once in the proxy, once in the render. JWKS itself is cached process-wide (`GLOBAL_JWKS`, `GoTrueClient.js:56`), so the asymmetric path is free after warm-up. | Confirm the Supabase project uses ES256/RS256 signing keys, not the legacy HS256 secret. If it is on HS256, migrate to asymmetric keys before launch - it is a two-network-hop tax on every request that no frontend change can remove. Independently: the proxy has already verified the token; `getServerAuth` could decode-and-trust rather than re-verify, but only if the proxy matcher is guaranteed to cover the route (it is, per `src/proxy.ts:20`). |
| 12 | **Low** | `server-cache-react` | `src/api/server.ts:83-85`, `102-104`, `120`, `122-124`, `128`, `147-149` | `export const loadMembers = cache((query: Query) => get<Page<Member>>("/members/", query));` | `React.cache` compares arguments with `Object.is`, so every one of these object-keyed loaders is a guaranteed cache miss across two call sites. I checked every route and **found no render that calls the same object-keyed loader twice**, so this is latent rather than active. It is worth flagging because the codebase already knows about it and solved it properly for the two loaders where it bit (`lookupMembers` and `membersAtCompanies` take a joined string key, `src/api/server.ts:174-178,205-211`) - the same discipline was not extended to the rest. | Either leave it and keep the comment at `src/api/server.ts:174-177` as the standing warning, or normalise: `const loadMembersByKey = cache((key: string) => get(...JSON.parse(key)))` with a stable-sorted stringify wrapper. Low value until two components actually want the same list. |
| 13 | **Low** | `async-suspense-boundaries` | `src/app/(app)/layout.tsx:14-22`, `src/app/layout.tsx:48` | `const { accessToken } = await getIdentity();` then `await Promise.all([...])`, with no `<Suspense>` anywhere in either layout | Page segments stream fine - `(app)/loading.tsx` is the nearest boundary for every route that lacks its own, so `/`, `/members/[slug]`, `/events`, `/announcements`, `/network`, `/companies` and `/me` all get a skeleton. But the two layouts themselves are outside every boundary, so the shell's first byte waits on `getIdentity()` plus the slowest of `me`/`member`/`announcements` - which is the 50-announcement fetch from #3. | Wrap the header's data-dependent bits in the layout in their own `<Suspense>` and hand `AppShell` a promise for `unread`/`name`, or fix #3 so the blocking fetch stops being the slow one. #3 is the cheaper fix and gets most of the benefit. |
| 14 | **Nit** | `bundle-analyzable-paths` (adjacent) | `src/app/next.config.ts:1-10` | `const nextConfig: NextConfig = { output: "export", images: { unoptimized: true } };` | Dead file. Next reads `next.config.ts` from the project root only, and the real one at `frontend/next.config.ts:107-110` explicitly documents that `output: "export"` is gone. This stale copy sits inside `src/app/`, contradicts the live config, and will mislead the next reader (and any agent) into thinking the app is a static export. | Delete `src/app/next.config.ts`. |
| 15 | **Nit** | n/a (dead code) | `src/components/MemberGrid.tsx`, `MemberModal.tsx`, `MemberTile.tsx`, `Toolbar.tsx` | `MemberGrid` is imported by nothing outside its own subtree; the four form one unreferenced island | No bundle cost (unreferenced modules are tree-shaken), but four `"use client"` files that look like the directory UI and are not. Confusing for the same reason as #14. | Delete, or note in `frontend/README.md` why they are kept. |

---

## Per-route request chains

Notation: `->` is a serial hop; `‖` is concurrent. Counts are **server -> FastAPI HTTP round
trips per page view**, after `React.cache` deduplication within the render (which is shared
across `generateMetadata`, layout and page, per the Next docs cited above).

Constant prefix on every route: `proxy.getClaims()` (`src/proxy.ts:10`) -> then the root layout's
`getIdentity()` and the `(app)` layout / page segments render **in parallel**.

Layout cost, signed in: 3 requests (`/auth/me`, `/members/me`, `/announcements/?limit=50`),
issued as one `Promise.all` (`(app)/layout.tsx:16-22`).
Layout cost, signed out: **0** - guarded by `accessToken ?` on line 16, which is
`async-cheap-condition-before-await` done right.

### `/` (home) - heaviest route

```
proxy.getClaims
  -> [ layout: Promise.all(me, myMember, announcements)            (3 reqs)
     ‖ MemberGate: getIdentity -> loadMe                           (0 new, dedup w/ layout)
     ]
  -> Feed: Promise.all(me*, myMember*, myIntents, mySaved,
                       announcements*, events, jobs, housing)       (5 new; * = dedup)
  -> wave 2: Promise.all( members?intent=<focus>&limit=5,
                          members/lookup?ids=...,
                          companies/{id} x0..3 )                    (2-5)
```

**Depth 3, 10-13 requests signed in. 0 requests signed out** (the gate renders the sign-in
notice without touching the backend). Hop 1 (`MemberGate`'s `loadMe`) is removable per #2.

### `/members/[slug]`

```
proxy.getClaims
  -> [ layout (3) ‖ generateMetadata: loadMember(slug) (1) ‖ gate: loadMe (0, dedup) ]
  -> Profile: Promise.all(loadMember(slug)*, loadMemberPath(slug))   (1 new)
```
**Depth 2, 5 requests.** `loadMember` is deduped between `generateMetadata` and `Profile`, as
the comment at `members/[slug]/page.tsx:12-15` claims - verified correct.

### `/jobs`

```
proxy.getClaims
  -> [ layout (3, signed in only) ‖ Promise.all(jobs?limit=100, companies?limit=100) ]
  -> Promise.all(members/lookup, members/at-company)
```
**Depth 2. 7 signed in, 4 signed out** - and the 4 signed-out ones should be 0 on a warm Data
Cache, which #1 currently prevents. No `MemberGate`, so this route is already flat.

### `/jobs/[slug]`

```
proxy.getClaims
  -> [ layout (3) ‖ generateMetadata: loadJobByRef (1)
                  ‖ Promise.all(loadJobByRef*, loadCompanyMap -> companies?limit=100) (1) ]
  -> loadMemberIndex([posted_by])                                    (1)
  -> [stream] PeopleAtCompany: members?company=<name>&limit=6        (1)
```
**Depth 4 signed in, 7 requests. 4 signed out.** The last two hops are serialized by #7; the
`PeopleAtCompany` boundary could start at hop 2.

### `/housing`

```
proxy.getClaims -> [ layout (3) ‖ gate: loadMe ] -> housing?limit=100 -> members/lookup
```
**Depth 3, 5 requests.** Two removable-ish hops: the gate (#2) and the byline (#9).

### `/housing/[id]`

```
proxy.getClaims
  -> [ layout (3) ‖ generateMetadata: loadHousingListing (1) ‖ gate: loadMe (0) ]
  -> Promise.all(loadHousingListing*, loadMe*)                      (0 new)
  -> loadMemberIndex([member_id])                                   (1)
  -> [stream, parallel] members?location=<city>  ‖  housing?city=<city>   (2)
```
**Depth 4, 7 requests.** Hop 3 needlessly gates hop 4 (#7).

### `/paths`

```
proxy.getClaims -> [ layout (3) ‖ gate: loadMe ]
  -> Promise.all(paths/flow, paths/groups, members/facets)          (3)
--- hydration ---
  -> browser: /api/auth/dev-session (or supabase getSession) -> POST-free GET /paths/flow  (duplicate)
```
**Depth 2, 6 server requests + 1 duplicated client request** for the single most expensive
endpoint on the site (#4).

### `/events`, `/events/[id]`

`proxy -> [layout (3) ‖ gate] -> events?upcoming=..&limit=100`. **Depth 2, 4 requests.**
`events/[id]` is the same shape with `loadEvent` deduped between `generateMetadata` and the
`<Suspense>`-wrapped `Event`. Both hand `initial` into React Query correctly, so no client
refetch on first paint.

### `/me`

```
proxy.getClaims -> [ layout (3) ‖ gate: loadMe (0, dedup) ]
--- HTML sent, nothing user-specific in the body ---
  -> browser: restore session (1 round trip)
  -> browser: GET /auth/me ‖ GET /members/me                        (2)
  -> browser: GET /members/me/entry (default tab)                   (1)
```
**3 server requests, then a 3-hop client waterfall for data the server already had** (#5). The
worst first-paint-to-content on the site.

### `/post`, `/network`, `/announcements`

All **depth 1, 3 requests** (everything deduped against the layout). `/post`'s `loadMe()` at
`post/page.tsx:36` is free; `/announcements` `Promise.all`s two already-cached reads. These are
the cleanest routes in the app.

### `/companies`

`proxy -> [layout (3, signed in) ‖ Promise.all(companies?limit=100, jobs?limit=100)]`.
**Depth 1. 5 signed in, 2 signed out** (should be 0 warm, see #1).

### `/login`, `/onboarding`, `/auth/callback`, `/api/auth/dev-session`

`/login`: **0 backend requests** on the server; the roster type-ahead is client-side and
unauthenticated. `/onboarding`: 0 server requests (`getIdentity` + `redirect`), then client
fetches `/auth/me` and `/members/facets`. `/auth/callback`: one `exchangeCodeForSession` to
Supabase, no backend call, correctly ordered. `/api/auth/dev-session`: pure cookie I/O, no
awaitable work worth deferring.

### Totals

| Route | Signed in | Signed out | Serial depth (signed in) |
|---|---|---|---|
| `/` | 10-13 | 0 | 3 |
| `/members/[slug]` | 5 | 0 | 2 |
| `/jobs` | 7 | 4 (should be 0 warm) | 2 |
| `/jobs/[slug]` | 7 | 4 (should be ~2 warm) | 4 |
| `/housing` | 5 | 0 | 3 |
| `/housing/[id]` | 7 | 0 | 4 |
| `/paths` | 6 (+1 client dup) | 0 | 2 |
| `/events` | 4 | 0 | 2 |
| `/events/[id]` | 4 | 0 | 2 |
| `/companies` | 5 | 2 (should be 0 warm) | 1 |
| `/announcements` | 3 | 0 | 1 |
| `/network` | 3 | 0 | 1 |
| `/post` | 3 | 0 | 1 |
| `/me` | 3 (+3 client hops) | 0 | 1 server, 3 client |
| `/login`, `/onboarding` | 0 | 0 | 0 |

Plus, on every one of them, 2 Supabase `getClaims` calls (proxy + render) which are local
verifications on an asymmetric-key project and network calls on an HS256 one (#11).

---

## Answers to the specific questions

**2. Does the layout header fetch block the page stream?** No, and this is the one thing that
looked bad and is not. The Next 16 docs (`06-fetching-data.md:458`) confirm layouts and pages
render in parallel, so `(app)/layout.tsx`'s three fetches do not delay the page segment's
fetches. What they *do* block is the shell flush, because neither layout sits inside a Suspense
boundary (#13). Page-level streaming is well covered: `(app)/loading.tsx` is the nearest
boundary for all seven routes without their own `loading.tsx`, and there are dedicated ones for
`jobs`, `jobs/[slug]`, `housing`, `housing/[id]`, `paths`, `post`. **No route is missing a
loading boundary.**

**3. `React.cache` key-by-identity:** the issue exists in the type signatures (#12) but I could
not find a single render where it actually causes a duplicate request. The two loaders where it
would have hurt - the member id lookup and the at-company lookup - already take a joined,
sorted string key precisely for this reason (`src/api/server.ts:174-178`, `205-211`). Duplicate
requests per render: **none found on the server**. On the client there is one (#4, `/paths`) and
one whole page of them (#5, `/me`).

**4. `fetch` cache semantics:** the `accessToken ? no-store : revalidate` split at
`src/api/server.ts:56-63` is exactly right - personalised reads must never be shared, public
reads opt in. The problem is that the three routes those revalidate windows were written for
disable the Data Cache at the segment level (#1). And note the structural consequence: for a
signed-in member, `revalidate` is unreachable by construction, so `/jobs` and `/companies` are
fully live for the audience that actually uses them. That is correct as written (the token
changes the response), but it means the ISR windows only ever serve anonymous traffic - worth
knowing before anyone tunes them.

**6. Module-level mutable server state:** **clean, verified.** `src/api/client.ts:25`
(`let accessToken`) is reachable only from `"use client"` modules - I traced all seven importers
(`AuthProvider.tsx`, `useAsk.ts`, and the five `api/hooks/*.ts`, every one of which begins with
`"use client"`). More importantly, `"use client"` does not prevent SSR execution, so I also
checked the *writer*: `setAccessToken` is called only from `apply` (`AuthProvider.tsx:67`),
which is invoked only from a `useEffect` and from event handlers (lines 85, 110, 113, 169, 185)
- never during render. So the module variable is never written on the server. The three
server-only modules (`api/server.ts`, `auth/session.ts`, `lib/supabase/server.ts`) all carry
`import "server-only"` and hold nothing at module scope. `providers.tsx:20` creates the
QueryClient in `useState` rather than at module scope, with a comment saying why. This rule is
fully satisfied.

**7. `after()`:** nothing in the codebase needs it. There are no Server Actions (`"use server"`
appears nowhere), no server-side logging or analytics, and the one fire-and-forget-shaped
operation - marking an announcement read - is already an optimistic client mutation
(`src/api/hooks/community.ts:165-204`). No finding.

**8. `generateMetadata` duplicating page fetches:** **no duplication.** All four
(`members/[slug]:16`, `jobs/[slug]:26`, `housing/[id]:20`, `events/[id]:14`) call
`React.cache`-wrapped loaders with primitive arguments, and the Next docs confirm memoization is
shared between `generateMetadata` and the page. Each of them is one request, not two, and the
comments claiming so are accurate.

**`server-auth-actions`:** not applicable - there are no Server Actions. Authorization is
enforced server-side in FastAPI (`AGENTS.md`: "Authorization lives in `application/`, never in a
router") and the frontend gate is presentation only, which is the right split.

**`server-hoist-static-io`:** not applicable - no filesystem or static-asset I/O in any route
handler or server component. The CDTM logo is a plain `<img src="/assets/cdtm.svg">`
(`AppShell.tsx:66`).

---

## What is already done well

This codebase has clearly been through a performance pass, and most of it holds up.

- **Signed-out visitors cost nothing.** `(app)/layout.tsx:16` and `MemberGate.tsx:36` both check
  the cheap synchronous `accessToken` before awaiting anything. A signed-out hit on `/`,
  `/housing` or `/paths` makes **zero** backend requests. That is
  `async-cheap-condition-before-await` applied correctly, twice, on the hot path.
- **The batched lookups are the right fix, and the cache key is right.** `loadMemberIndex` and
  `loadMembersAtCompanies` (`src/api/server.ts:160-247`) replaced what the comments say used to
  be "eleven pages of directory" and "one request per distinct company" with one batched call
  each, and they join their ids into a sorted string so `React.cache` actually hits. Batches
  within them go out via `Promise.all` (lines 189, 221). This is textbook.
- **`Promise.all` is used consistently and correctly** wherever the operations are genuinely
  independent: `(app)/layout.tsx:16`, `(app)/page.tsx:47` (8-way), `page.tsx:69` (second wave),
  `paths/page.tsx:18`, `jobs/page.tsx:29` and `:48`, `companies/page.tsx:32`,
  `announcements/page.tsx:22`, `members/[slug]/page.tsx:45`, `housing/[id]/page.tsx:48`. I did
  not find a single accidental sequential `await` pair that could have been a `Promise.all`.
- **Flattening at the RSC boundary is deliberate and thorough.** `toJobRow`
  (`src/features/jobboard/jobData.ts:49`) turns a `Job` + `Company` + two `Member`s into a
  17-field flat row with a comment explaining why; `HousingCardData`
  (`housing/page.tsx:27-50`) and `CompanyCardData` (`companies/page.tsx:44-57`) do the same.
  `AppShell` takes four scalars rather than the account object (`AppShell.tsx:37-39`). The one
  slip is the home page's announcements (#6).
- **The 10k-line `schema.d.ts` costs nothing at runtime.** Every reference to it is
  `import type` (`api/client.ts:5`, `api/types.ts`, `auth/contract.ts:1`), so it is erased at
  compile time. This was worth checking and is a non-issue.
- **Placeholders were deliberately split out of the client bundle.**
  `src/components/placeholders.tsx:1-10` explains that `LoadingBlock`/`EmptyState` live apart
  from `states.tsx` because the latter is a client module and importing it "used to drag these
  two skeletons into the browser bundle of nineteen files". That is a real, well-reasoned fix.
- **Streaming boundaries are used where they earn their keep.** `PeopleAtCompany`
  (`jobs/[slug]:220`), `MembersInCity` / `AlsoInCity` (`housing/[id]:188,194`) and the event body
  (`events/[id]:33`) are all suspended so a dependent read does not hold the page. The
  `next/dynamic` split of `PathsChart` (`PathsExplorer.tsx:20`, `AskExplorer.tsx:22`) with
  `ssr: false` is correct for an SVG chart nothing above the fold needs.
- **The Supabase session handling is right.** No client at module scope in either
  `lib/supabase/server.ts:16` or `lib/supabase/proxy.ts:23`, both with comments naming the
  concurrency hazard; the proxy's "nothing may run between `createServerClient` and
  `getClaims`" comment (`proxy.ts:45-47`) is a real trap correctly avoided; `getServerAuth` uses
  `getClaims` (signature-verified) for identity and `getSession` only for the raw token to
  forward, and says so.
- **`initialData` seeding is already the house pattern** for events and announcements
  (`api/hooks/community.ts:31-39,42-52,138-146`), with the reasoning written down. `/paths` and
  `/me` are the two places it was not applied (#4, #5), which makes them straightforward fixes
  rather than new architecture.
- **`loadJobByRef` avoids a failed request plus a retry** by testing the segment shape against a
  UUID regex (`src/api/server.ts:136-146`) instead of trying one endpoint and falling back.
- **The home feed already fixed its own worst waterfall**: `(app)/page.tsx:63-65` reads at most
  three companies by id rather than pulling a hundred to name three. `jobs/[slug]` is the one
  page that did not get the same treatment (#8).

### Suggested order of work

1. Remove the three `force-dynamic` exports (#1) - one-line change, largest measurable win, and
   it is currently silently contradicting its own comment.
2. Seed `usePathFlow` with `initialFlow` (#4) - halves the cost of the heaviest endpoint.
3. Add an unread-count endpoint (#3) - removes a 50-row fetch from every page in the app.
4. Start page data before `MemberGate` awaits (#2) - removes one serial hop from 15 routes.
5. Seed `/me` from the server (#5) - biggest perceived-latency win for the signed-in user.
6. Move the poster lookups into their own boundaries (#7).
