# CDTM Community frontend, performance audit

Next.js 16.3.1 (Turbopack) / React 19.2.8 / Tailwind 4. Audited against the Vercel
react-best-practices rules `bundle-*` and `rendering-*` in
`/Users/krishuagarwal/.claude/skills/react-best-practices/rules/`.

Everything below is measured off a real production build unless it says "static analysis".

---

## 1. Measurements

### 1.1 The repo build fails (blocker, not a perf finding)

`cd frontend && npm run build` compiles but then fails the type check:

```
✓ Compiled successfully in 3.9s
  Running TypeScript ...
src/app/login/LoginForm.tsx(94,49): error TS2339: Property 'email' does not exist on type
  '{ class_label?: string | null | undefined; id: string; name: string; slug: string; }'.
src/app/login/LoginForm.tsx(94,72): error TS2339: Property 'email' does not exist on type
  '{ class_label?: string | null | undefined; id: string; name: string; slug: string; }'.
Failed to type check.
```

`LoginForm.tsx:94` reads `picked?.email` off the dev member-picker row, and the generated
`DevMemberPublic` in `src/api/schema.d.ts` has no `email`. No production build can be
produced from the tree as it stands.

To get route and chunk numbers I copied the frontend into the scratchpad
(`scratchpad/fe-build`, hardlinked `node_modules`, symlinked `public`, `.env.local` as
committed) and added only `typescript: { ignoreBuildErrors: true }` to that copy's
`next.config.ts`. No tracked file in the repo was touched (`git status --porcelain frontend/`
is empty). That build succeeds:

```
✓ Compiled successfully in 12.5s
✓ Generating static pages using 9 workers (18/18) in 1399ms
```

`.env.local` sets `NEXT_PUBLIC_AUTH_MODE=dev`, but `src/auth/mode.ts::resolve()` returns
`"supabase"` unconditionally when `NODE_ENV === "production"`, so **every production build is
a Supabase-auth build** regardless of the env var. The dev-vs-supabase question in the brief
therefore does not change what ships.

### 1.2 Route table

Next 16 no longer prints size columns, so First Load JS is computed from
`.next/build-manifest.json` (`rootMainFiles`) plus the non-`async` chunks in each route's
`server/app/**/page_client-reference-manifest.js`, summing the real bytes on disk.

The polyfill chunk `0cz1d0mv5g_q7.js` (110.0 kB raw / 38.5 kB gzip, core-js) is served with
`noModule`: verified in `.next/server/app/_global-error.html`: so no modern browser fetches
it. It is excluded from the numbers below; add 110.0 kB raw / 38.5 kB gzip for legacy.

Every route is `ƒ` dynamic (server-rendered on demand) except `○ /icon.svg`. There is a
Proxy (middleware).

| Route | Rendering | First Load JS (raw) | gzip | route-only raw |
|---|---|---|---|---|
| `/housing/[id]/edit` | dynamic | 541.9 kB | 164.4 kB | 113.2 kB |
| `/housing/new` | dynamic | 541.1 kB | 164.4 kB | 112.4 kB |
| `/jobs/new` | dynamic | 539.8 kB | 164.0 kB | 111.1 kB |
| `/housing` | dynamic | 538.5 kB | 164.0 kB | 109.8 kB |
| `/network` | dynamic | 537.7 kB | 162.6 kB | 109.0 kB |
| `/paths` | dynamic | 537.1 kB | 162.6 kB | 108.4 kB |
| `/me` | dynamic | 533.4 kB | 160.5 kB | 104.7 kB |
| `/housing/[id]` | dynamic | 532.1 kB | 161.3 kB | 103.4 kB |
| `/members/[slug]` | dynamic | 527.3 kB | 159.1 kB | 98.6 kB |
| `/jobs` | dynamic (`force-dynamic`) | 524.9 kB | 159.1 kB | 96.3 kB |
| `/jobs/[slug]` | dynamic | 523.2 kB | 158.9 kB | 94.6 kB |
| `/` | dynamic | 523.0 kB | 157.9 kB | 94.4 kB |
| `/announcements` | dynamic | 521.7 kB | 157.3 kB | 93.0 kB |
| `/events` | dynamic | 520.6 kB | 157.1 kB | 91.9 kB |
| `/events/[id]` | dynamic | 519.9 kB | 156.8 kB | 91.2 kB |
| `/events/new` | dynamic | 519.8 kB | 156.7 kB | 91.1 kB |
| `/companies` | dynamic | 511.6 kB | 154.6 kB | 82.9 kB |
| `/post` | dynamic | 508.0 kB | 153.1 kB | 79.3 kB |
| `/onboarding` | dynamic | 505.5 kB | 150.7 kB | 76.8 kB |
| `/login` | dynamic | 504.8 kB | 151.6 kB | 76.1 kB |
| `/_not-found` | dynamic | 492.0 kB | 146.5 kB | 63.3 kB |
| `/auth/callback`, `/api/auth/dev-session` | route handlers | 428.7 kB | 126.5 kB | 0 kB |

**Shared by every route: 428.7 kB raw / 126.5 kB gzip.** CSS: one file,
`3fp-u4td7xxnd.css`, 55.2 kB raw / 11.2 kB gzip.

The spread across routes is narrow (63 to 113 kB of route-specific JS). Nothing is a bundle
outlier; the shared framework baseline dominates.

### 1.3 Largest client chunks and what is in them

`.next/static/chunks` holds 39 files, 1.4 MB total.

| Chunk | Raw | gzip | Contains | In first load? |
|---|---|---|---|---|
| `2pm69m7q_3vmm.js` | 251.7 kB | 66.0 kB | `@supabase/ssr` + `@supabase/supabase-js` (GoTrueClient, RealtimeClient markers present) | **No**: async only |
| `37ukl2sboo9lr.js` | 234.2 kB | 71.3 kB | `react-dom` client (`hydrateRoot`, `useSyncExternalStore`) | Yes, shared |
| `36mqrch1rud5d.js` | 160.1 kB | 42.6 kB | Next App Router client runtime | Yes, shared |
| `0cz1d0mv5g_q7.js` | 112.6 kB | 38.5 kB | core-js polyfills | `noModule`, legacy only |
| `1_h2dgbtnvnuj.js` | 38.0 kB | 12.8 kB | `@tanstack/react-query` (`QueryClient`, `queryKey`) + app client entry | Yes, all 21 pages |
| `2mmpezlrfmbu5.js` | 34.7 kB | 8.5 kB | Next client bootstrap | Yes, shared |
| `008qyzb-f72wl.js` | 25.1 kB |: | app-common client modules; **the only referrer of the Supabase chunk** | Yes, all 21 pages |
| `2hft-qijekqot.js` … `1b9ur2xl4dxu4.js` | 3.6 to 33.9 kB |: | one per route, correctly split | Route-only |
| `094px2au4eavx.js` / `2d6jw_ujncpdp.js` | 3.8 / 6.2 kB |: | `PathsChart` via `next/dynamic`, once for `/paths` and once for `/network` | No, lazy |

**Is `@supabase/supabase-js` in the shared first-load bundle? No.** It is reachable only
through `import()` from `008qyzb-f72wl.js`. `src/auth/AuthProvider.tsx:95-98,127,182` and
`src/auth/session.ts:48` all use dynamic `import("@/lib/supabase/client")`, and
`src/lib/supabase/client.ts` is the only client module that touches the package. It appears in
no route's `clientModules` chunk list and in no `react-loadable-manifest.json`. This is
correct and deliberate.

**But it is still fetched on every route right after hydration.** In a production build
`isDevAuth` is false, so `AuthProvider`'s restore effect (`AuthProvider.tsx:94-116`) fires
`import("@/lib/supabase/client")` on mount on every page, then `supabase.auth.getSession()`.
That is 251.7 kB raw / 66.0 kB gzip on the critical path to the first authenticated API call,
requested only after the main bundle has parsed and hydrated: with no `modulepreload` hint.

### 1.4 `src/api/schema.d.ts` (10,754 lines)

Types-only, confirmed. Every one of the five importers uses `import type`:

- `src/api/client.ts:5`: `import type { paths }`
- `src/api/types.ts:1`: `import type { components, operations }`
- `src/api/media.ts:2`: `import type { components, operations }`
- `src/auth/contract.ts:1`: `import type { components }`
- `src/features/community/ask/types.ts:1`: `import type { components }`

No `openapi-typescript` runtime marker appears in any emitted chunk. Zero bytes shipped.

### 1.5 Image inventory

| Call site | Element | Source | Optimizer? | Attributes |
|---|---|---|---|---|
| `components/MemberAvatar.tsx:52` | `<img>` | `/avatars/*.webp` (static, ingest-produced 160/400px) | **No** | `width`/`height`, `loading` eager\|lazy, `fetchPriority`, `decoding="sync"`, blur as CSS background |
| `components/AppShell.tsx:66` | `<img>` | `/assets/cdtm.svg` | No | `width=32 height=32`, eager |
| `app/login/LoginForm.tsx:57` | `<img>` | `/assets/cdtm.svg` | No | `width=32 height=32`, eager |
| `features/jobboard/CompanyLogo.tsx:40` | `<img>` | `logo.clearbit.com` or pasted URL | No | `width`/`height`, `loading="lazy"`, `decoding="async"`, `onError` fallback |
| `app/onboarding/OnboardingForm.tsx:120` | `<img>` | `*.googleusercontent.com` | No | `width=48 height=48` |
| `features/community/housing/HousingCard.tsx:56` | `next/image` | API `/api/v1/media/**` | **Yes** | `fill`, `sizes` set, **no `priority`** |
| `app/(app)/housing/[id]/page.tsx:87` | `next/image` | API media | Yes | `fill`, `sizes`, `priority` on index 0 |
| `app/(app)/housing/[id]/page.tsx:257` | `next/image` | API media | Yes | `fill`, `sizes="64px"` |
| `app/(app)/jobs/[slug]/page.tsx:75` | `next/image` | API media | Yes | `fill`, `sizes`, `priority` |
| `components/ImageUpload.tsx:108` | `next/image` | API media | **No** (`unoptimized`) | `width=96 height=72` |

**Member avatars do not go through `/_next/image`.** They are plain `<img>` against
pre-resized static WebPs in `public/avatars` (1,250 files, 12 MB). That is the right call:
routing 2,500 already-optimal WebPs through the optimizer would buy nothing and cost a
sharp() pass and a cache entry each.

**Uploaded media does go through the optimizer.** `mediaUrl()` (`src/api/media.ts:26`)
absolutises to `${NEXT_PUBLIC_API_URL}/api/v1/media/...`, allowed by
`next.config.ts` `images.remotePatterns[0]`. Headers this needs from the FastAPI side, all
present: `backend/media/api/router.py:138` returns the bytes with the correct
`media_type` and `Cache-Control: public, max-age=31536000, immutable`
(`router.py:45`), and the endpoint is deliberately unauthenticated, so the Next server can
fetch it without forwarding a bearer token. Nothing to fix there.

`remotePatterns` also allows `logo.clearbit.com` and `**.googleusercontent.com`, but no
`next/image` ever points at either: both are plain `<img>`. Those two entries are dead
config (the CSP `img-src` entries next to them are the ones doing the work).

### 1.6 Fonts

No web font at all. `src/app/globals.css:15` defines
`--font-display: "Avenir Next", Avenir, "Nunito Sans", ui-sans-serif, system-ui, sans-serif`
and `globals.css:45` applies it to `body`. There is no `next/font`, no `@font-face`, no
`fonts.googleapis.com`/`fonts.gstatic.com` link, and `.next/static/media` contains exactly one
file (`icon.33sn_gy4e7-ln.svg`, 1,002 bytes). Zero font bytes, zero render-blocking font
requests, no FOIT/FOUT. `font-src 'self' data:` in the CSP matches.

### 1.7 Third-party scripts and analytics

None. `grep` for `next/script`, `<script`, `dangerouslySetInnerHTML`, `<link` across `src/`
returns nothing. No analytics, no error tracker, no tag manager. `rendering-script-defer-async`
and `bundle-defer-third-party` have nothing to act on.

### 1.8 CSS

One stylesheet, `src/app/globals.css`, 1,648 lines / 35,201 bytes of source, compiling to a
single 55.2 kB raw / 11.2 kB gzip Tailwind 4 output. Twelve `style={{...}}` sites in the whole
tree, all tiny (avatar box size, progress-bar width, legend swatches, skeleton
`animationDelay`). Nothing large or inline-injected.

### 1.9 DOM size of the long lists

`MemberGrid.tsx` (`PAGE = 150`, growing by 150 to all 1,250 members) is **dead code**: no
route imports it. Verified: `MemberGrid` has no importer, and it is the sole importer of
`MemberModal`, `Toolbar` and `lib/profiles.ts`. Had it been mounted, a full page would be
~10 elements per `MemberTile` × 150 = ~1,500 elements, reaching ~12,500 at 1,250 members.

The lists that actually render:

| List | Server cap | Per-row markup | Full-page elements | Virtualized / `content-visibility` |
|---|---|---|---|---|
| `JobsBrowser` → `JobRow` | `limit: 100` (`jobs/page.tsx:31`) | ~25 elements | ~2,500 | `.cv-row` per row, `contain-intrinsic-size: auto 88px` |
| `HousingBrowser` → `HousingCard` | `limit: 100` (`housing/page.tsx:19`) | ~20 elements | ~2,000 | `.cv-card` per card, `contain-intrinsic-size: auto 320px` |
| `AskExplorer` member list | LLM answer size | ~18 elements | small | `.cv-row` per row |
| `PathsExplorer` member lists | API page | ~12 elements | small | `.cv-row` per row |
| `EventList` | `limit: 100` (`api/server.ts:97`) | ~14 elements | ~1,400 | **none** |
| `AnnouncementList` | `limit: 50` (`api/server.ts:94`) | ~12 elements | ~600 | **none** |

No windowing library anywhere; `content-visibility` is the whole strategy, which is the right
one at these sizes.

### 1.10 Hydration

`app/layout.tsx:48` awaits `getIdentity()` and passes `initialEmail` / `initialSignedIn` into
`Providers` → `AuthProvider`, and `(app)/layout.tsx` passes `signedIn`, `name`, `avatarUrl`,
`unread` into `AppShell` as server-resolved scalars. The first client paint already shows the
signed-in header; there is no signed-out flash and no `localStorage` read on the render path.

`components/RelativeTime.tsx:30` uses `useSyncExternalStore(noop, () => true, () => false)` so
server and first client render both print the absolute date and the relative wording is swapped
in exactly once after hydration. `Typewriter.tsx:83-92` does the same for
`prefers-reduced-motion`. There is not a single `typeof window` branch in `src/` and not a
single `suppressHydrationWarning`: neither is needed, because both known mismatches are
handled with `useSyncExternalStore` instead. This is the correct pattern, better than the
`suppressHydrationWarning` the rule allows.

---

## 2. Findings

| Severity | Rule id | Location | Evidence | Impact | Recommended fix |
|---|---|---|---|---|---|
| **Critical** | `rendering-svg-precision` | `frontend/public/assets/cdtm.svg`, used at `src/components/AppShell.tsx:66` and `src/app/login/LoginForm.tsx:57` | The file is 1,168,266 bytes. Bytes 2,590 to 1,167,577 (**1,164,987 bytes, 1.11 MB**) are a single `<i:pgf id="adobe_illustrator_pgf">` CDATA blob (base64 zlib, starts `eJzs`) inside `<switch><foreignObject requiredExtensions="&ns_ai;">`, which no browser renders. The actual drawn geometry is 5 `<polygon>` and 2 `<path>` elements totalling **2,598 bytes**. It is served eagerly, in the header, at `width=32 height=32`, on every page. Compression barely helps: gzip 884 kB, brotli 876 kB. | ~1.11 MB / ~876 kB over the wire on first visit: **more bytes than the entire JS + CSS payload of any route combined** (428.7 kB raw / 126.5 kB gzip JS + 11.2 kB gzip CSS). At 5 Mbps that is ~1.4 s of transfer contending with the hydration bundle, and it is an in-viewport `<img>` so it competes at high priority. | Run `npx svgo --multipass --precision=1 public/assets/cdtm.svg`, or hand-strip the `<switch>`/`<foreignObject>`/`<i:pgf>` block and the Adobe DTD entities. Result is ~2.6 kB. Better still, inline the 7-shape logo as a hoisted JSX `<svg>` constant so it costs zero requests. |
| **High** | `rendering-usetransition-loading`, `rerender-use-deferred-value` | `src/features/jobboard/JobsBrowser.tsx:65,213-214` with `src/lib/urlState.ts:23-39`; same shape in `src/features/community/housing/HousingBrowser.tsx` | The jobs search box is a controlled input whose `value` is `params.get("q")` and whose `onChange` calls `setQuery` → `setParams` → `router.replace()`. `/jobs` carries `export const dynamic = "force-dynamic"` (`jobs/page.tsx:16`), so a search-param change is a full App Router navigation with an RSC refetch, and the server component then issues four upstream FastAPI calls (`loadJobs` limit 100, `loadCompanies` limit 100, `loadMemberIndex`, `loadMembersAtCompanies`). One per keystroke. (Code-verified; not measured live, there is no backend running here.) | Every keystroke: one RSC round trip + 4 API calls + a re-render of up to 100 `JobRow`s (~2,500 elements) on the same tick as the input update. Typing "berlin" is 6 navigations. Expect visible input lag well past the 200 ms INP budget on anything but localhost. | Keep the typed text in local `useState` for immediate echo, push it to the URL inside `startTransition` (or on a debounce/`useDeferredValue`), and feed the *deferred* value to the filter `useMemo`. `MemberGrid.tsx:57` already demonstrates the `useDeferredValue` pattern the browsers should copy. |
| **High** | `rendering-resource-hints` | `src/app/layout.tsx` (no hint present); origin from `src/api/config.ts:2` | The FastAPI backend is a **separate origin** (`NEXT_PUBLIC_API_URL`, e.g. another host in a deployment) and is `connect-src`-allowed in the CSP. Every client hook in `src/api/hooks/*` fetches it after hydration, and `next/image` fetches uploaded media from it server-side. There is no `preconnect`, no `prefetchDNS`, no `<link rel="preconnect">` anywhere in `src/`. Same for the Supabase origin in supabase mode. | The first client API call pays full DNS + TCP + TLS. Typically 100 to 300 ms on a cold mobile connection, serialized in front of every client-side query and in front of the Supabase `getSession()` handshake. | In `src/app/layout.tsx` (a server component, so the hints go out with the HTML): `import { preconnect, prefetchDNS } from "react-dom"` and call `preconnect(API_BASE_URL)` plus `preconnect(SUPABASE_URL)` when configured. |
| **High** | `bundle-preload` | `src/auth/AuthProvider.tsx:94-116` | In any production build `isDevAuth` is false (`src/auth/mode.ts:24`), so the restore effect dynamically imports `@/lib/supabase/client` on mount of **every** route. That resolves to the 251.7 kB raw / 66.0 kB gzip Supabase chunk, requested only after the main bundle parses and hydrates, with no `modulepreload`. Until it lands, `setAccessToken` has not been called and every gated query is unauthenticated. | 66 kB gzip on the critical path to first authenticated data, starting one full round trip after hydration rather than in parallel with it. Adds roughly one RTT + 66 kB of transfer to time-to-first-data on every cold page load. | The code split is right: keep it. Add the hint: `preloadModule`/`preinitModule` from `react-dom` in the root layout, or a `<link rel="modulepreload">` for the chunk, so it downloads alongside the main bundle. Alternatively kick the `import()` off at module scope of the client entry rather than inside the effect. |
| **Medium** | `bundle-conditional` | `src/proxy.ts:9-11` → `src/lib/supabase/proxy.ts:19,48` | The proxy runs `createServerClient(...)` and `await supabase.auth.getClaims()` on every request that is not a static asset: including every RSC navigation and every `/api/*` route. It short-circuits on `isSupabaseConfigured`, i.e. on whether the URL and key env vars exist, **not** on `isSupabaseAuth`. `.env.example` explicitly tells you to set `NEXT_PUBLIC_SUPABASE_URL` even in dev-auth mode, so a dev-auth deployment still pays for the Supabase refresh on every request. | One extra auth verification per request in front of every page render. With a symmetric (legacy anon/HS256) project `getClaims()` reaches the Supabase Auth server, so this is a network round trip added to TTFB on every navigation. | Gate on `isSupabaseAuth` from `src/auth/mode.ts`, not on `isSupabaseConfigured`. In dev-auth mode return `NextResponse.next()` before the import is even reached, and move `import { updateSession }` behind a dynamic `import()` so the Supabase code never enters the proxy bundle for a dev-auth build. |
| **Medium** | `server-parallel-fetching` (adjacent), `rendering-conditional-render` | `src/app/(app)/layout.tsx:16-22` | The shared layout calls `loadAnnouncements()` on every route in the `(app)` group. `api/server.ts:94` fetches `/announcements/?limit=50` with `cache: "no-store"`, and the layout uses exactly one field of the result: `announcements?.unread`. `/jobs`, `/companies`, `/paths`, `/housing` etc. all pay for a 50-item announcements payload to render a badge number. | One unnecessary uncached API call plus a 50-item JSON body on every single navigation. On a slow backend link this is added TTFB on routes that never show an announcement. (`React.cache` dedupes it with the announcements page's own call, so only the other ~18 routes pay.) | Add an `/announcements/unread-count` endpoint (or `limit=0` returning just `{unread}`) and call that from the layout. |
| **Medium** | `rendering-content-visibility` | `src/features/community/events/EventList.tsx:19` (`EventRow` `<li>`), `src/features/community/announcements/AnnouncementList.tsx` (`AnnouncementCard` `<li>`) | Every other long list in the app tags its rows `.cv-row` / `.cv-card`. These two do not, and both are served with generous caps: events `limit: 100` (`api/server.ts:97`), announcements `limit: 50` (`api/server.ts:94`). Full lists are roughly 1,400 and 600 elements, all laid out and painted up front. | With ~6 rows visible, the browser lays out and paints ~94 events and ~44 announcements it will never show. Per the rule's own figure that is roughly a 10× initial-render cost on those two routes. | Add `className="cv-row"` to `EventRow`'s `<li>` and `AnnouncementCard`'s `<li>`. The class and its `contain-intrinsic-size: auto 88px` already exist at `globals.css:1614-1617`; `AnnouncementCard` may want its own intrinsic size since it expands. |
| **Medium** | `rendering-content-visibility` | `src/features/jobboard/JobsBrowser.tsx:266`, `src/features/community/housing/HousingBrowser.tsx:163`, `src/features/community/ask/AskExplorer.tsx:194`, `src/features/community/paths/PathsExplorer.tsx:175,206` | These put `[content-visibility:auto]` on the **container** (`<ul>` / grid `<div>`) as well as on the rows. A container rule only skips work while the whole container is off-screen, which for the page's main list is essentially never; and the container carries no `contain-intrinsic-size`, so while it is briefly skipped its height collapses to zero. | No measurable win, and a scroll-height jump risk on first paint / on back-navigation restore. The per-row `.cv-row`/`.cv-card` classes are what is actually doing the work. | Drop `[content-visibility:auto]` from the five container elements and keep it on the rows. |
| **Medium** | `bundle-dynamic-imports` (image path) | `src/features/community/housing/HousingCard.tsx:56` | `next/image` with `fill` and correct `sizes`, but no `priority` on the first card. `next/image` defaults to `loading="lazy"`, so the largest above-the-fold element on `/housing` is discovered only after layout. `housing/[id]` and `jobs/[slug]` both get this right (`priority` on index 0). | LCP on `/housing` is delayed by roughly one image round trip, commonly 200 to 500 ms. | Thread an `index`/`priority` prop from `HousingBrowser` and set `priority` on the first one or two cards. |
| **Medium** | (image decode, adjacent to `rendering-content-visibility`) | `src/components/MemberAvatar.tsx:57` | `decoding="sync"` on every avatar. In a list this forces the decode of each image onto the main thread at paint time instead of letting the browser do it off-thread. `CompanyLogo.tsx:46` correctly uses `decoding="async"`. | Long-task risk proportional to how many avatars land in one frame: the housing byline avatars, the `/network` answer list, the saved-people rail. Each 160px WebP decode is on the order of 1 to 3 ms of main thread. | Use `decoding="sync"` only where `priority` is true (where it does buy a flash-free first paint) and `decoding="async"` otherwise. |
| **Low** | `bundle-dynamic-imports` | `src/features/community/paths/PathsExplorer.tsx:20` and `src/features/community/ask/AskExplorer.tsx:22` | `PathsChart` is correctly `next/dynamic`-ed in both places, but the two `import()` specifiers (`"./PathsChart"` and `"@/features/community/paths/PathsChart"`) produce two separate lazy chunks: `094px2au4eavx.js` (3.8 kB) for `/paths` and `2d6jw_ujncpdp.js` (6.2 kB) for `/network`. | ~4 to 6 kB duplicated, and no chunk reuse when a visitor moves between the two routes. Small. | Use one specifier: the `@/…` form: in both files so Turbopack emits one shared chunk. |
| **Low** | `bundle-analyzable-paths` (dead weight) | `src/components/MemberGrid.tsx`, `MemberTile.tsx`, `MemberModal.tsx`, `Toolbar.tsx`, `src/lib/profiles.ts` | No route imports `MemberGrid`; it is the only importer of the other four. `lib/profiles.ts:23` fetches `/profiles/{id}.json`, and `public/profiles/` holds 1,115 JSON files (11 MB) plus `public/data/index.json` (1.26 MB) that nothing else reads. | Zero runtime cost (correctly tree-shaken: none of these appear in any route's chunk list), but ~12.3 MB of dead files in every deployment image and slower `next build` file tracing. Note the 1,250 avatar WebPs in `public/avatars` are **not** dead: `MemberAvatar` serves them. | Delete the five modules and `public/data/index.json` + `public/profiles/` if the roster grid is genuinely retired, or wire `MemberGrid` back into a route if it is not. **Do not touch `public/avatars`.** |
| **Low** | `rendering-hoist-jsx` | `src/components/placeholders.tsx:12-27` | `LoadingBlock` rebuilds its `Array.from({ length: rows })` skeleton on every render and gives each row an inline `style={{ animationDelay }}`. It is rendered from 21 call sites. No React Compiler is configured in `next.config.ts`, so nothing hoists it automatically. | Small: a handful of allocations per loading state. | Hoist the common `rows={2}`/`rows={3}`/`rows={4}` variants to module-level constants, or enable `reactCompiler` in `next.config.ts` and let it do this everywhere. |
| **Nit** | `bundle-analyzable-paths` | `frontend/src/app/next.config.ts` | A stray `next.config.ts` containing `images: { unoptimized: true }` sits **inside the App Router directory**. It is not the config Next reads (the real one is `frontend/next.config.ts`, and the build log confirms `✓ Running next.config.ts took 49ms` against the root file), and it is not a route file, so Next ignores it. | None at runtime. It is a trap: it reads as if image optimization were off app-wide, which is the opposite of what ships. | Delete it. |
| **Nit** | `bundle-conditional` | `frontend/next.config.ts:27-33` | `remotePatterns` allows `logo.clearbit.com` and `**.googleusercontent.com`, but every consumer of those hosts (`CompanyLogo.tsx:40`, `OnboardingForm.tsx:120`) uses a plain `<img>`, never `next/image`. | None. Dead config that widens the optimizer's allowed-host surface for no benefit. | Drop both patterns (keep the matching CSP `img-src` entries, which are load-bearing). |
| **Nit** | `rendering-script-defer-async` |: | No `<script>` tags, no `next/script`, no analytics anywhere in `src/`. |: | Nothing to do. Keep it that way; if analytics is added later, follow `bundle-defer-third-party`. |
| **Nit** | `bundle-barrel-imports` | `frontend/package.json` | No barrel-heavy dependency is installed. The runtime deps are `@supabase/ssr`, `@supabase/supabase-js`, `@tanstack/react-query`, `next`, `openapi-fetch`, `react`, `react-dom`, `server-only`. No icon library, no `lodash`, no `date-fns`. All icons are hand-written inline SVG. | None. | No `optimizePackageImports` entry is needed. |

---

## 3. What is already done well

- **The Supabase SDK is genuinely code-split.** `AuthProvider.tsx:95-98,127,182` and
  `session.ts:48` reach it only through `import()`, and `lib/supabase/client.ts` is the sole
  client module that touches it. Verified against the build: the 251.7 kB chunk appears in no
  route's first-load set and is referenced only from the shared app-common chunk. This is the
  single biggest bundle decision in the app and it was made correctly.
- **`PathsChart` and its Sankey layout are `next/dynamic` with `ssr: false` and a real
  skeleton fallback**, on both routes that draw it. `bundle-dynamic-imports` satisfied.
- **No web fonts.** A system-first stack in `globals.css:15` means zero font requests and no
  FOIT/FOUT. `.next/static/media` holds one 1 kB SVG and nothing else.
- **No third-party JavaScript at all.** No analytics, no tag manager, no error tracker.
- **Hydration is handled the hard, correct way.** `RelativeTime.tsx:30` and
  `Typewriter.tsx:83-92` both use `useSyncExternalStore` with a server snapshot rather than a
  `useEffect` + `setState` flip or a `suppressHydrationWarning` band-aid. `layout.tsx:48` and
  `(app)/layout.tsx:26-29` seed the signed-in state from the server, so `AppShell` never
  flashes the signed-out header. There is not one `typeof window` branch in the tree.
- **`schema.d.ts` is disciplined.** All 10,754 lines are behind `import type` in all five
  importers; nothing reaches a chunk.
- **Member avatars bypass the image optimizer on purpose**, served as ingest-produced 160 px
  and 400 px WebPs with `width`/`height` set, `loading="eager"` + `fetchPriority="high"` for
  the first `PRIORITY_COUNT = 12` tiles and lazy after, plus a blur data-URL painted as the
  `<img>`'s own background so there is no two-element handover flash
  (`MemberAvatar.tsx:49-70`). This is a better design than routing 2,500 pre-sized files
  through `/_next/image`.
- **Uploaded media through `next/image` is correctly configured on both ends**: `sizes` on
  every `fill` image, and the FastAPI endpoint returns
  `Cache-Control: public, max-age=31536000, immutable` (`backend/media/api/router.py:45,138`)
  so the optimizer caches rather than re-encoding.
- **`ImageUpload.tsx:113` marks its previews `unoptimized`**: right call for a transient
  upload thumbnail that would otherwise cost an optimizer pass per file.
- **`content-visibility` is used at all**, with `contain-intrinsic-size` on both classes
  (`globals.css:1613-1622`), on the rows of four of the six long lists.
- **Server data loading is careful.** Every loader in `api/server.ts` is wrapped in
  `React.cache`, nothing is held at module scope, and each page fans out with `Promise.all`
  (`(app)/page.tsx:46-56` does eight reads in one wave, then three dependent ones in a
  second). `loadMemberIndex` batches id lookups 50 at a time in parallel
  (`api/server.ts:LOOKUP_BATCH`) instead of one request per row.
- **Route-level code splitting is clean.** Every route has its own 3.6 to 33.9 kB chunk and the
  spread of route-specific JS is only 63 to 113 kB. There is no accidental shared blob.
- **`placeholders.tsx` was deliberately split from `states.tsx`** so 21 server components can
  render skeletons without dragging a client module into their bundles: the comment at
  `placeholders.tsx:5-10` shows this was a considered fix, and the build confirms it worked.
- **Numeric conditional rendering is safe throughout.** `AppShell.tsx:93` uses `unread > 0 &&`,
  and a sweep for `{x.length &&` / `{count &&` patterns found none. `rendering-conditional-render`
  is clean.
- **The CSP is tight and the proxy matcher excludes `_next/static`, `_next/image`, `assets`,
  `avatars`, `profiles` and every image extension**, so static assets never pay for the
  session refresh.
