# Frontend performance audit, remaining items (agent 3)

Scope: /Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend. Nothing committed.

## 1. rendering-hoist-jsx: LoadingBlock rows (implemented)

Validated: `src/components/placeholders.tsx:16-24` (pre-edit) rebuilt `Array.from({ length: rows })`
plus a fresh `style` object per row on every render. `grep -rn "LoadingBlock" src | wc -l` reports 25
references across 21 files, all passing literal counts (2, 3, 4, or the default 3). No React Compiler
in the build (`next.config.ts` has no `reactCompiler` flag, `package.json` has no babel plugin), so
nothing memoizes this automatically.

Changed: added a module-level `ROWS_BY_COUNT` Map and a `skeletonRows(count)` helper that builds the
row array once per distinct count and reuses it. `LoadingBlock` now renders `{skeletonRows(rows)}`.
Markup, class names, keys and the 80ms stagger are byte-identical.

Files: `src/components/placeholders.tsx:12-40`.

## 2. bundle-dynamic-imports: one specifier for PathsChart (implemented)

Validated: `src/features/community/ask/AskExplorer.tsx:22` imports
`@/features/community/paths/PathsChart`, `src/features/community/paths/PathsExplorer.tsx:20` imported
`./PathsChart`. Same file, two specifiers.

Changed: `PathsExplorer.tsx:20` now uses the `@/features/community/paths/PathsChart` specifier, with a
short comment saying why the aliased spelling is deliberate. Build is clean; whether Turbopack was
actually emitting two chunks or deduping by resolved id, the two call sites now agree.

Files: `src/features/community/paths/PathsExplorer.tsx:18-23`.

## 3. bundle-conditional: dead remotePatterns (implemented)

Validated: every `next/image` consumer is `src/app/(app)/jobs/[slug]/page.tsx:70` (cover, `mediaUrl`),
`src/app/(app)/housing/[id]/page.tsx:105` and `:295` (photos, `mediaUrl` or picsum),
`src/features/community/housing/HousingCard.tsx`, `src/components/ImageUpload.tsx` (previews). The two
hosts in question are drawn with a plain `<img>`: `src/features/jobboard/CompanyLogo.tsx:39` (clearbit
logos) and `src/app/onboarding/OnboardingForm.tsx:87-90` (Google avatar, with a comment saying exactly
that). `me.account.avatar_url` (googleusercontent) reaches `MemberAvatar` from
`src/app/(app)/layout.tsx:32` and `src/app/(app)/page.tsx:136`, and `src/components/MemberAvatar.tsx`
does not import `next/image` either. So neither host can reach the optimizer.

Changed: removed the `logo.clearbit.com` and `**.googleusercontent.com` entries from
`remotePatterns` and rewrote the file header comment (four sources became three, with a line naming the
two plain-`<img>` hosts). The CSP `img-src` entries for both hosts are untouched: they are what
actually permits those images.

Files: `next.config.ts:3-22`.

## 4. rerender-split-combined-hooks: token out of the session context (implemented)

Validated: `src/auth/AuthProvider.tsx:15` had `token` in `AuthState` and `:223` had it in the memo deps,
so every token refresh produced a new context value. Consumers: `src/api/hooks/shared.ts:15`
(`signedIn`, `loading`, used by `useAuthedQueryOptions`, which every gated query and every SaveButton
reaches), `src/app/login/LoginForm.tsx:27`, `src/app/(app)/me/Client.tsx:60`,
`src/app/onboarding/OnboardingForm.tsx:27`. The only reader of `token` in the whole tree is
`src/components/ImageUpload.tsx:47`. `src/api/client.ts` exposes `setAccessToken` only, no getter, so
the second option in the brief was not available without adding one.

Changed: split into two providers. `AuthState` no longer carries `token`; a new `TokenContext` holds it,
nested inside `AuthContext.Provider`, and a new `useAccessToken()` hook reads it. `useSession()` keeps
its name, its guard and every other field, so `shared.ts`, `LoginForm`, `me/Client` and
`OnboardingForm` are unchanged. `ImageUpload` switched to `useAccessToken()`; its `accept` callback and
dependency array are otherwise untouched (the token still has to be a value there, since `uploadMedia`
in `src/api/media.ts:36-48` takes it as an argument and sets the header on its own XHR).

Files: `src/auth/AuthProvider.tsx:12-36, 209-238`, `src/components/ImageUpload.tsx:7, 47-49`.

## 5. Supabase restore: drop the redundant getSession (implemented)

Validated in `node_modules/@supabase/auth-js` 2.112.3,
`dist/main/GoTrueClient.js:3617-3671`: `onAuthStateChange` registers the subscriber, then awaits
`initializePromise` and calls `_emitInitialSession(id)`, which emits `INITIAL_SESSION` with the restored
session, or `INITIAL_SESSION, null` if the restore throws. So the pre-edit sequence at
`AuthProvider.tsx:130-136` committed the same session twice on mount (one `apply` from `getSession()`,
one from `INITIAL_SESSION`).

Changed: removed the `getSession()` call and its `active` guard; `INITIAL_SESSION` is now the restore
path and is what clears `loading`. Both failure paths still work: an unconfigured environment returns
before the subscription (`AuthProvider.tsx:124-128` clears `loading` and sets `configured`), and a
failed restore still delivers `INITIAL_SESSION, null`, which `apply(null, null)` turns into a
signed-out, non-loading state. Unmount before the emission is safe: the cleanup calls
`listener.subscription.unsubscribe()`, which deletes the emitter, and `_emitInitialSession` looks the
id up in `stateChangeEmitters` before invoking it.

Files: `src/auth/AuthProvider.tsx:127-136`.

## 6. Typewriter: pause in a hidden tab (implemented, small)

Validated: `src/features/community/ask/Typewriter.tsx:38-45` schedules a timer per character
(TYPE_MS 45, DELETE_MS 22), so roughly 22 state updates a second, forever, on every page that renders
`AskLine` (network, jobs, housing, paths).

Changed: added `useDocumentVisible()`, the same `useSyncExternalStore` shape as the existing
`useReducedMotion()` (server snapshot `true`), and gated only the effect on it
(`if (!animate || !visible) return;`, `visible` added to the deps). Rendered output is untouched: text
and cursor still key off `animate`, so nothing changes on screen when the tab is hidden or when it comes
back, and the existing `prefers-reduced-motion` handling and the WCAG 2.2.2 stop button are unchanged.
Nine lines total.

Files: `src/features/community/ask/Typewriter.tsx:31-49, 95-105`.

## 7. async-suspense-boundaries on /housing (skipped, cannot be done without editing HousingBrowser)

Validated: the earlier agent already did half of it. `src/app/(app)/housing/page.tsx:14-19` is a
synchronous component that calls `gatedData(loadBoard)` and hands the promise to a child inside
`MemberGate`, so the board's reads go out alongside the gate's `/auth/me` rather than behind it
(`src/components/MemberGate.tsx:40-44`). What is still serial is inside `loadBoard`
(`housing/page.tsx:23-33`): `loadHousing(...)` then `loadMemberIndex(listings.items.map(...))`. That
second call is inherently dependent, the member ids come off the listings, so it cannot be
parallelised, only deferred.

Skipped, with reason: the bylines cannot stream separately without changing `HousingBrowser`'s props.
Its contract is `{ listings: HousingCardData[] }` (`HousingBrowser.tsx:33`), and `postedBy` is a field
inside each `HousingCardData` (built at `housing/page.tsx:40-62`), consumed by `HousingCard`. Both files
are under `src/features/community/housing/`, which is off limits. Every possible shape of the fix
(passing a members promise or a second byline map, or rendering the board once without bylines and
again with them) either changes that prop contract or re-mounts `HousingBrowser` and throws away its
local filter state (`kind`, `city`, and the ask input at `HousingBrowser.tsx:44-45`). Left alone for
whoever owns those files.

Files: none.

## 8a. getIdentity out of the root layout (skipped)

Validated: `src/app/layout.tsx:59` awaits `getIdentity()`, which reads `cookies()` in both modes
(`src/auth/session.ts:27-51`), and every server loader calls `getAccessToken()` before its fetch
(`src/api/server.ts:51`). The only routes outside `(app)` are `/login` and `/onboarding`
(`find src/app -maxdepth 3 -name page.tsx`), and everything under `(app)` goes through
`src/app/(app)/layout.tsx:17`, which awaits `getIdentity()` itself. The production build confirms it:
every route except `/icon.svg` is already `ƒ (Dynamic)`.

Skipped for two reasons. Nothing under `(app)` could become static regardless, since the `(app)` layout
and the loaders read cookies on their own, so the move buys exactly two routes. And those two are the
ones that need the value: `initialEmail` from the root layout is what
`src/app/onboarding/OnboardingForm.tsx:27` reads through `useSession()`, and `initialSignedIn` is what
keeps `/login` (`LoginForm.tsx:27`) from flashing the signed-out state. Moving the read into
`(app)/layout.tsx` would leave both of them without a server-verified session on first paint, which is
a regression for no measurable gain.

## 8b. Seeding `loading` from `initialSignedIn` (skipped, not safe)

Validated: the bearer token is module state in `src/api/client.ts:26-36`, and the request middleware
attaches `Authorization` only `if (accessToken)`. It is populated exclusively by `setAccessToken`, which
only `AuthProvider.apply` calls (`AuthProvider.tsx:82-88`), and `apply` cannot run before the Supabase
client chunk has loaded and `INITIAL_SESSION` has arrived. `useAuthedQueryOptions`
(`src/api/hooks/shared.ts:15-17`) is the only thing holding those queries back.

Skipped: seeding `loading = !initialSignedIn` would let every gated query fire during hydration, before
`setAccessToken` has run, so each one would go out with no `Authorization` header and 401. The retry
policy in `shared.ts:18-24` deliberately does not retry auth failures, so the result would be a page of
permanently failed queries, not a slower one. The existing comments in `client.ts` and in
`AuthProvider.apply` describe this same ordering hazard.

## Verification

`npm run typecheck`

```
> cdtm-community@0.1.0 typecheck
> tsc --noEmit
```

`npm run lint`

```
> cdtm-community@0.1.0 lint
> eslint
```

`npm run build` (tail)

```
✓ Compiled successfully in 3.3s
  Running TypeScript ...
  Finished TypeScript in 11.8s ...
✓ Generating static pages using 9 workers (21/21) in 920ms
  Finalizing page optimization ...

Route (app)
┌ ƒ /
├ ƒ /_not-found
├ ƒ /announcements
├ ƒ /api/auth/dev-session
├ ƒ /auth/callback
├ ƒ /companies
├ ƒ /directory
├ ƒ /events
├ ƒ /events/[id]
├ ƒ /events/new
├ ƒ /housing
├ ƒ /housing/[id]
├ ƒ /housing/[id]/edit
├ ƒ /housing/new
├ ○ /icon.svg
├ ƒ /jobs
├ ƒ /jobs/[slug]
├ ƒ /jobs/new
├ ƒ /login
├ ƒ /me
├ ƒ /members/[slug]
├ ƒ /network
├ ƒ /onboarding
├ ƒ /paths
└ ƒ /post

ƒ Proxy (Middleware)
```

## Files touched

- `next.config.ts`
- `src/components/placeholders.tsx`
- `src/features/community/paths/PathsExplorer.tsx`
- `src/auth/AuthProvider.tsx`
- `src/components/ImageUpload.tsx`
- `src/features/community/ask/Typewriter.tsx`

Nothing on the off-limits list was modified, and nothing else in the working tree was reformatted or
reverted.
