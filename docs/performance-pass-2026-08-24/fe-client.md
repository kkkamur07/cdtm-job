# Frontend client-side performance audit

Scope: `frontend/src`: data fetching (TanStack Query 5 + openapi-fetch), re-renders, JS hot paths.
Method: Vercel React best-practices skill, every rule file with prefix `client-`, `rerender-`, `js-`,
`advanced-` read and checked against the code. Every file listed in the brief was read in full.

Two facts that set the baseline for everything below:

- **React Compiler is not enabled.** `frontend/next.config.ts` has no `reactCompiler` flag and no
  babel plugin. Manual memoization is therefore load-bearing.
- **`memo()` appears zero times in the codebase.** `grep -rn "\bmemo(" src/` returns nothing. So does
  `useTransition` / `startTransition`. `useDeferredValue` appears once, in a module nothing imports.

## Findings

| Severity | Rule id | Location (file:line) | Evidence | Impact | Recommended fix |
| --- | --- | --- | --- | --- | --- |
| **Critical** | rerender-defer-reads, rerender-transitions | `frontend/src/features/jobboard/JobsBrowser.tsx:60,65,213-215` + `frontend/src/lib/urlState.ts:36` | `const query = params.get("q") ?? ""` … `const setQuery = (value: string) => setParams({ q: value })` … `<input value={query} onChange={(event) => setQuery(event.target.value)} />`, and `setParams` ends in `router.replace(...)` | The jobs search box is fully URL-driven with no debounce. Every keystroke fires `router.replace`, and `frontend/src/app/(app)/jobs/page.tsx:16` is `export const dynamic = "force-dynamic"`, so each replace refetches the whole RSC payload and re-runs `JobsPage()`. Two of that page's four upstream calls (`loadMemberIndex`, `loadMembersAtCompanies`) go out with `cache: "no-store"` (`frontend/src/api/server.ts:60-62`: no `revalidate` option means no-store), so typing "product manager" = 15 RSC round trips and 30 uncached backend calls. Worse, `value` comes from `params`, which Next only updates when the transition commits, so on a slow link characters visibly lag and revert. | Keep the typed value in local state (`useState`), render from that, and push it to the URL only on a debounce (`lib/useDebounced.ts` already exists) or inside `startTransition`. The filtering itself is in-memory over `pool`, so it needs no URL round trip at all: the URL only needs the settled value for shareability. |
| **High** | rerender-functional-setstate | `frontend/src/components/ImageUpload.tsx:55-78`, esp. `:72` | `for (const file of chosen) { … const result = await uploadMedia(...); onChange(multiple ? [...urls, result.url] : [result.url]) }`: the comment on `:71` claims "Functional update" but `urls` is the prop captured at render time | Dropping three photos onto a housing listing keeps only the last one. Each loop iteration awaits, then spreads the *same stale* `urls` array, so upload 2 overwrites upload 1. This is a correctness bug, not only a perf one. | Accumulate locally (`const added: string[] = []`) and call `onChange([...urls, ...added])` once after the loop, or lift to a functional-updater-shaped callback `onChange(prev => [...prev, url])` and change the prop contract. |
| **High** | rerender-memo | `frontend/src/features/community/ask/AskExplorer.tsx:195-205` and `:224-280`; `frontend/src/features/jobboard/JobsBrowser.tsx:267-269`; `frontend/src/features/community/housing/HousingBrowser.tsx:164-166` | `{members.map((member) => <ResultRow key={member.id} … onSelect={() => setSelectedId(…)} />)}`: `ResultRow` is a plain function, and `onSelect` is a fresh closure per row per render | Nothing in the app is memoized. Clicking one row in Ask re-renders all 24 rows; each one re-runs `whyMatched()` (`features/community/ask/filters.ts:118-167`, six `toLowerCase()` + `includes` passes over the member) and re-renders a `SaveButton` that itself subscribes to the `mySaved` query. Same shape on Jobs (`JobRow`) and Housing (`HousingCard`). | `const ResultRow = memo(function ResultRow(…))`, pass `onSelect` as a stable `useCallback` taking the id (`onSelect(member.id)`) rather than a per-row closure, and memoize `reasons` inside the row. Same treatment for `JobRow` and `HousingCard`. |
| **High** | js-index-maps | `frontend/src/features/community/paths/layout.ts:147-148` calling `:216-229` | `const sourceTotal = totalFor(links, link.source_stage, link.source_group, "source") \|\| 1;` and `totalFor` is `(links ?? []).filter(…).reduce(…)` | The Sankey layout is O(L²): `totalFor` walks the entire `links` array, and it is called twice for every link. It is the answer to "is the layout O(n²)": yes. For the /paths flow (4 stages × up to 8 groups) that is tens of thousands of comparisons per layout, and the layout re-runs whenever `flow` or `perPerson` changes, including every class-filter change. | One pass before the loop building `Map<string, number>` for source totals and another for target totals, then `sourceTotals.get(key) ?? 1`. Turns O(L²) into O(L). |
| **Medium-High** | js-cache-function-results, js-hoist-regexp | `frontend/src/lib/format.ts:71-103, 132-137, 175, 190, 209-215` | `date.toLocaleDateString(LOCALE, { day:"numeric", month:"short", year:"numeric", timeZone: ZONE })`; `const fmt = (n) => new Intl.NumberFormat(LOCALE, {…}).format(n)`; `formatPrice` builds a `new Intl.NumberFormat` on every call | Answering question 8 directly: there are **no** module-level cached `Intl` formatters. `Date.prototype.toLocaleDateString/String` with an options object constructs a fresh `Intl.DateTimeFormat` internally each call, which is one of the most expensive things in the standard library. `EventRow` (`features/community/events/EventList.tsx:16,31`) does three of them per row and the events list fetches `limit: 100`; `HousingCard` (`features/community/housing/HousingCard.tsx:45-47`) does three per card; `RelativeTime` (`components/RelativeTime.tsx:32,37`) does two per instance and is used in every announcement and intro row. `dateRange` also calls `new Date()` per invocation just to read the current year. | Hoist `const DATE = new Intl.DateTimeFormat(LOCALE, {…})` etc. to module scope, one per option shape, and call `.format(date)`. Hoist the `thisYear` read out of `dateRange`. Same for the `Intl.NumberFormat`s in `formatSalary`, `compactSalary`, `formatPrice`. Also hoist the regex literals in `initials` (`:43`, evaluated once per name part), `slugify` (`:249-254`, six per call) and `paragraphs` (`:295`): `js-hoist-regexp`. |
| **Medium** | async-dependencies (client waterfall) | `frontend/src/api/hooks/shared.ts:14-25` + `frontend/src/auth/AuthProvider.tsx:55,77-122` | `return { enabled: !loading && signedIn, … }` where `const [loading, setLoading] = useState(true)` and `loading` only clears after `fetch("/api/auth/dev-session")` or `supabase.auth.getSession()` resolves | Answering the `enabled`-gating question: yes, there is one real sequential waterfall, and it is global. No authed client query can start until an auth round trip finishes, even though the server already knows the identity and passes `initialSignedIn` down (`app/providers.tsx:39`). On /paths that means auth round trip → `usePathFlow` → then `usePathMembers` on click. Most list screens hide it behind server-rendered `initialData`; the ones that do not (`usePathFlow`, `useAsk`, `useFacets`) pay it in full. | The token itself must be fetched, but the *gate* need not wait: seed `loading` from `initialSignedIn` where the server has already vouched for the session, or let the query fire and let `client.ts`'s request-time token read (`api/client.ts:25-36`, already written for exactly this) supply the header. |
| **Medium** | client-swr-dedup (duplicate fetch) | `frontend/src/features/community/paths/PathsExplorer.tsx:55,62` vs `frontend/src/api/hooks/community.ts:268-276` | `const flow = usePathFlow(classId ? { class_id: classId } : {});` … `const shown = asked ? … : (flow.data ?? initialFlow);`: `usePathFlow` takes no `initialData` | The server already loaded the unfiltered flow and handed it in as `initialFlow` (`app/(app)/paths/page.tsx:18-22,36`), yet the client immediately refetches the identical payload on mount. `useEvents` and `useAnnouncements` do this correctly (`api/hooks/community.ts:31-39,138-146` both take `initialData`); paths is the odd one out. Every visit to /paths costs one redundant full-flow request. | Add an `initialData` parameter to `usePathFlow` and pass `initialFlow` when `classId` is undefined, exactly as `useEvents` does. |
| **Medium** | rerender-split-combined-hooks, rerender-defer-reads | `frontend/src/auth/AuthProvider.tsx:189-202` + `frontend/src/api/hooks/shared.ts:15` | `useMemo<AuthState>(() => ({ mode, token, email, signedIn, loading, configured, … }), [token, email, signedIn, loading, …])` and `const { signedIn, loading } = useSession()` | The context value is memoized, so a re-render of `AuthProvider` itself does not re-render `children` (the element identity is stable). But `token` sits in the same object as `signedIn`/`loading`, and **every** authed query hook reads that context through `useAuthedQueryOptions`. On a Supabase token refresh (`onAuthStateChange` at `:112-114` → `apply` → `setToken`) the value identity changes and every consumer re-renders. On /network that is ~25 components (24 `SaveButton`s, each holding `useMySaved`, plus the explorer). `ImageUpload:38` is the only consumer that genuinely wants `token`. | Split the context in two: a rarely-changing `{ signedIn, loading, configured, mode, …actions }` that gates queries, and a separate `token` context (or drop the token from context entirely: `api/client.ts` already holds it in module state and `uploadMedia` could read it from there). |
| **Medium** | rerender-memo, js-tosorted-immutable | `frontend/src/features/jobboard/CompanyPicker.tsx:31` | `const options = [...(companies.data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name));`: no `useMemo` | `CompanyPicker` is a child of `PostJobForm` (`app/(app)/jobs/new/Client.tsx:100`), which keeps all fields in one `form` state object, so it re-renders on every keystroke in the title, description and every other field. Each of those keystrokes re-sorts up to 100 companies with `localeCompare` (the fetch asks for `limit: 100`, `api/hooks/jobboard.ts:37`) and rebuilds 100 `<option>` elements. Typing a job description is the worst case. | `useMemo(() => [...items].toSorted(byName), [items])`, and wrap `CompanyPicker` in `memo`: `value` and `onChange` are already stable (`setCompanyId`). |
| **Medium** | js-batch-dom-css (paint blocking) | `frontend/src/components/MemberAvatar.tsx:57` | `decoding="sync"` on every avatar `<img>` | `decoding="sync"` tells the browser to decode the image on the main thread before it can present the frame. It is set unconditionally, including for the lazily-loaded avatars in long lists (`AvatarCircle` is used in Ask results, saved list, intros, housing cards, job rows, people strip). Where a screenful of avatars arrives at once this serialises the decodes onto the main thread and stalls scrolling. | Keep `decoding="sync"` only where `priority` is true (the first screenful, where it prevents a flash) and use `decoding="async"` otherwise. |
| **Medium** | rerender-transitions | `frontend/src/features/community/housing/HousingBrowser.tsx:39-41,113,126,143` and `frontend/src/app/(app)/me/Client.tsx:44,121` | `const setKind = (value: string) => setParams({ kind: value === "all" ? null : value })`; `onClick={() => setTab(item.key)}` | Same `router.replace` mechanism as the Critical finding, but driven by clicks rather than keystrokes, so the cost is one RSC round trip per chip/tab click instead of per character. `/housing` is not `force-dynamic` but its server loaders are `no-store` (`api/server.ts:102-104` plus the `loadMemberIndex` follow-up at `app/(app)/housing/page.tsx:23`), so each city chip costs two backend calls to re-derive data the client already holds in `listings`. Switching tabs on /me does the same. | Wrap the `router.replace` in `useUrlState` (`lib/urlState.ts:36`) in `startTransition` so the UI stays interactive, and mark the boards' filter state as local-first with the URL as a mirror. Alternatively raise `experimental.staleTimes.dynamic` so the client router cache absorbs repeat visits to the same URL. |
| **Low-Medium** | js-set-map-lookups | `frontend/src/features/community/SaveButton.tsx:40` | `const isSaved = Boolean(saved.data?.some((s) => s.saved.saved_member_id === memberId));` | O(shortlist) per row, and every `SaveButton` subscribes to the same query, so one save re-runs the scan in all of them. With 24 rows and a 50-person shortlist that is 1,200 comparisons per re-render: small in absolute terms, but it multiplies with finding 3. | Derive one `Set<string>` of saved ids with `useMemo` in the parent and pass `saved` down as a boolean, or use `useQuery`'s `select` to project the list into a `Set` once per cache entry. |
| **Low-Medium** | rerender-split-combined-hooks | `frontend/src/features/jobboard/JobsBrowser.tsx:105-123` | `const shown = useMemo(() => { const filtered = pool.filter(…); const by = {…}; return [...filtered].sort(by[sort]); }, [pool, query, selection, sort]);` | Changing the sort re-runs the filter, and the four-closure `by` object is re-allocated each time. `[...filtered]` also copies an array `.filter()` already made fresh. Tens of jobs, so the absolute cost is small, but it is the exact shape the rule warns about and it will bite when the board grows past the "hundred listings" the comment on `:44-45` anticipates. | Split into `filtered` and `shown` memos, hoist `by` to module scope, and drop the redundant spread (`filtered.sort(...)` is already safe, or use `toSorted`). |
| **Low** | rerender-transitions | `frontend/src/features/community/ask/Typewriter.tsx:38-45` | `const timer = setTimeout(() => setStep((current) => advance(current, phrases)), delay);` with `TYPE_MS = 45` | ~22 state updates per second, forever, on /network, /jobs, /housing and /paths. Answering the question directly: it is *not* a `setInterval` and it does **not** re-render a large tree: the state is local to `Typewriter`, its `phrases` props are module constants (`AskExplorer.tsx:27`, `JobsBrowser.tsx:14`, `HousingBrowser.tsx:11`) so the effect deps are stable, and the cleanup is correct. The cost is that it keeps the main thread from ever going idle and it competes with the RSC transitions above. It correctly stops under `prefers-reduced-motion`. | Acceptable as written. If the idle time matters, pause it when the tab is hidden or once the user has typed anything. |
| **Low** | client-swr-dedup | `frontend/src/api/hooks/community.ts:227,241,260` and `frontend/src/api/keys.ts:26-27` | `onSuccess: () => qc.invalidateQueries({ queryKey: ["housing"] })` while `housing: (params) => ["housing", params]` and `housingListing: (id) => ["housing", id]` share the same prefix | Creating, updating or renewing one listing invalidates every cached housing *detail* as well as every list, because both key shapes live under `["housing"]`. Not a storm today (one detail is usually cached) but it is invalidation by accident rather than by design. | Give details their own root: `housingListing: (id) => ["housing", "detail", id]`, and invalidate `["housing", "list"]` from the mutations. |
| **Low** | client-swr-dedup | `frontend/src/api/hooks/me.ts:189` | `onSuccess: () => qc.invalidateQueries({ queryKey: qk.mySaved })` after an optimistic write that already produced the correct row | Every save/unsave costs a full refetch of the shortlist immediately after the optimistic update landed. The comment on `:187-188` justifies it by the guessed `created_at`, which is honest, but the server response could supply it. | Write the server's returned row into the cache in `onSuccess` (as `useRsvp` does at `api/hooks/community.ts:117-127`) instead of invalidating. |
| **Low** | js-hoist-regexp | `frontend/src/features/community/announcements/AnnouncementList.tsx:52-54` | `return body.replace(/\s+/g, " ").trim().slice(0, 180);` | A new global `RegExp` per announcement per render. Fifty announcements are fetched (`api/hooks/community.ts:143`). Trivial in isolation; listed because it is the same rule as the `format.ts` entry and the fix is one line. | Hoist to `const WHITESPACE = /\s+/g;` at module scope. |
| **Low** | rerender-memo, js-cache-function-results, rerender-derived-state-no-effect | `frontend/src/components/MemberGrid.tsx:92-96, 98, 188-197` | `useEffect(() => { for (const m of filterWith(query).slice(0, PRELOAD_COUNT)) { if (m.avatar) preloadImage(m.avatar.sm, 0); } }, [query, filterWith]);` and `useEffect(() => setLimit(PAGE), [applied, classId, role]);` | **This module is dead code**: `grep -rn "MemberGrid" src/` shows it is imported by nothing, so it costs nothing at runtime and is tree-shaken out of the bundle. Recording it because it is the one place the brief asks about and because the problems are real if it is ever wired back up: (a) the preload effect runs a *second* full filter over ~1,250 members synchronously on every keystroke, at blocking priority, defeating the `useDeferredValue` on `:57`, and constructs 48 `new Image()` + `.decode()` + `Promise.race` per character; (b) `MemberTile` is unmemoized so all 150 tiles re-render twice per keystroke (urgent pass + deferred pass); (c) `setLimit` in an effect adds a third render pass per settled keystroke; (d) `members.find(...)` at `:109` is an O(n) scan per click. | Delete `MemberGrid.tsx`, `MemberTile.tsx`, `MemberModal.tsx`, `Toolbar.tsx`, `lib/profiles.ts` and `lib/types.ts` if the directory grid is not coming back. If it is: `memo(MemberTile)`, move the preload into the deferred pass and cap it, derive `limit` reset from a `key` on the grid rather than an effect, and index members by id once. |
| **Nit** |: | `frontend/src/api/hooks/members.ts:14`, `frontend/src/api/hooks/jobboard.ts:16`, `frontend/src/api/hooks/me.ts:40,101` | `useMember` and `useJobs` are exported and never called; `invalidateQueries({ queryKey: ["members"] })` targets a key no client query uses any more | Dead exports and no-op invalidations, left behind when the directory moved to server loaders (`api/hooks/members.ts:9-13` says so). No runtime cost, but they make the invalidation graph misleading to read. | Delete. |

## Answers to the specific questions

1. **Query keys** (`api/keys.ts`) are stable and fully parameterised: I found **no hook whose key omits a
   variable it sends**. The two near-misses are safe: `usePathMembers` adds a constant `limit: 60`
   (`api/hooks/community.ts:286`) and `useCompanies` a constant `limit: 100`
   (`api/hooks/jobboard.ts:37`). Object-literal params (`usePathFlow({})`, `useCompanies()`) are new
   objects per render but TanStack Query hashes keys structurally, so there is no refetch loop.
   `placeholderData: (previous) => previous` is set on the three list/flow queries that need it
   (`jobboard.ts:21,39`, `community.ts:274`) and on all three Ask queries (`useAsk.ts:32`), so typing
   never blanks a list. Global `staleTime: 30_000` and `refetchOnWindowFocus: false`
   (`app/providers.tsx:24-26`) are sensible. **`gcTime` is never set anywhere**: the 5-minute default
   applies, which is fine here. Optimistic updates exist and are well built for RSVP
   (`community.ts:81-128`), read receipts (`community.ts:165-204`), save/unsave (`me.ts:134-191`) and
   intro responses (`me.ts:216-244`), each with `cancelQueries`, a snapshot and an `onError` rollback.
   The only real waterfall is the global auth gate (finding 6); the only refetch-storm risks are the
   two Low findings above. No storms from mutation invalidation.

2. **Search/filter inputs**: `lib/useDebounced.ts` exists but is used in exactly one place, the dev
   sign-in roster picker (`app/login/LoginForm.tsx:162`): correctly, with `staleTime: 5 * 60 * 1000`
   on the query. The two real search boxes do **not** debounce. The jobs one round-trips the server
   per keystroke (Critical finding). The companies one (`app/(app)/companies/Client.tsx:32-42`) is the
   model to copy: local `useState`, in-memory `useMemo` filter, no URL, no network. The Ask bars
   (`AskLine.tsx:36`, `AskExplorer.tsx:50`) keep a local `draft` and only touch the URL on submit,
   which is right. `useDeferredValue` is used once, in dead code. `useTransition` / `startTransition`
   are used nowhere.

3. **AuthProvider**: the context value *is* memoized and `children` keeps a stable element identity,
   so a token refresh does **not** re-render the whole tree: only context consumers. But `token`
   shares the object with `signedIn`/`loading`, and every authed query hook consumes that context via
   `useAuthedQueryOptions`, so on each refresh every query-holding component re-renders (finding 8).
   `apply` (`AuthProvider.tsx:67-73`) is a stable `useCallback` firing five `setState`s that React 19
   batches, and it deliberately publishes the token to `api/client.ts` synchronously before setting
   state: the reasoning in the comment on `:58-66` is correct and worth keeping. The
   `onAuthStateChange` subscription has proper cleanup and an `active` guard.

4. **Lists**: keys are correct everywhere (stable ids, never array indices, except deliberately in
   `LoadingBlock`'s identical skeleton rows with a comment saying why, and in `MemberPositions.tsx:39`
   which falls back to the index only when `position.id` is null). No components are defined inside
   other components: `rerender-no-inline-components` is clean throughout; `Field`'s render-prop
   children (`components/Field.tsx:28`) look similar but are a function call, not a component type,
   so nothing remounts. No `.sort()` mutates a prop: every sort copies first
   (`JobsBrowser.tsx:122`, `CompanyPicker.tsx:31`, `OnboardingForm.tsx:68`, `layout.ts:142`), so
   `js-tosorted-immutable` is satisfied in substance. The problems are the missing `memo` (finding 3),
   the per-row callbacks, and the per-row `Intl` construction (finding 5).

5. **Paths**: the layout *is* computed in `useMemo` with correct deps (`PathsChart.tsx:48`,
   `[flow, perPerson]`), `flow` comes from the query cache so its identity is stable, and hover /
   selection state does **not** re-run the layout: `selected` is only read by `isHot`/`litRibbon` at
   `:60-67`, outside the memo. That part is right. It **is** O(n²) (finding 4). No SVG path is
   animated at all, so nothing triggers layout from animation. `layout.stages.map(... layout.nodes.find(...))`
   at `PathsChart.tsx:87` is a small second O(stages × nodes) scan. Changing `selected` re-renders
   every `Node`, since `Node` is unmemoized, but ~30 nodes is not worth chasing.

6. **Ask**: `useAsk`/`useJobAsk`/`useHousingAsk` are queries keyed on the trimmed question with a
   5-minute `staleTime`, `placeholderData` and a no-retry-on-4xx policy: a good design for POSTs that
   are semantically reads. `Typewriter` uses a self-rescheduling `setTimeout`, not a `setInterval`, and
   re-renders only itself (see Low finding). `filters.ts` is pure and cheap. `AskExplorer` keeps the
   draft local and only writes the URL on submit. The one thing to fix here is `ResultRow` memoization.

7. **Effects**: no derived-state-from-props effects in live code. The forms deliberately avoid the
   pattern by mounting the fields only once the server value is in hand
   (`EntryForm.tsx:52-57`, `IntentsForm.tsx:29-35`): this is exactly what
   `rerender-derived-state-no-effect` asks for and it is done well. No effect has an object or array
   dependency. Every timer and listener has cleanup: `Toolbar.tsx:62`, `Typewriter.tsx:44,88`,
   `SavedList.tsx:31-33`, `useDebounced.ts:15`, `MemberModal.tsx:58-61`, `AuthProvider.tsx:118-121`.
   The only global listeners are one `scroll` in `Toolbar` and one `matchMedia change` in
   `Typewriter`: both single-instance, so `client-event-listeners` (dedupe across N instances) does
   not apply. `lib/forms.ts:48` adds an `input` listener that removes itself on first fire.
   `advanced-effect-event-deps`, `advanced-event-handler-refs`, `advanced-use-latest` and
   `advanced-init-once`: no violations, and no `useEffectEvent` usage to get wrong.

8. **`lib/format.ts`**: no cached formatters, no hoisted regexes. See finding 5. This is the
   highest-leverage single-file fix in the audit.

9. **localStorage / sessionStorage**: **not used anywhere.** `grep -rn -E "localStorage|sessionStorage|document\.cookie|indexedDB" src/`
   returns only two comments. Supabase is configured cookie-backed rather than localStorage-backed
   (`lib/supabase/client.ts:12`) and the dev session lives in an httpOnly cookie. So
   `client-localstorage-schema` and `js-cache-storage` have nothing to flag: and the absence is the
   right answer, not an omission: it is what lets the server read the session.

10. **`ImageUpload.tsx`**: **no client-side resize** before upload: a 5 MB phone photo is sent as-is
    over `XMLHttpRequest` (`api/media.ts:36-80`); `checkImage` only rejects above 5 MB rather than
    downscaling. There is a progress bar, which is the right mitigation, but a `createImageBitmap` +
    `OffscreenCanvas` + `toBlob('image/webp', 0.8)` pass before `uploadMedia` would cut a typical
    upload by 5-10×. **Object URLs**: none are created: the component renders `mediaUrl(url)` from the
    server response, never a `blob:` preview: so there is nothing to revoke and no leak. The real
    defect here is the stale-closure multi-file bug (finding 2).

## What is already done well

- **Server-first data flow.** The heavy reads are done in `api/server.ts`, every loader wrapped in
  `React.cache`, nothing held at module scope, callers fanning out with `Promise.all`
  (`app/(app)/layout.tsx:16-22`, `app/(app)/paths/page.tsx:18-22`, `app/(app)/jobs/page.tsx:29-51`).
  The `React.cache`-keyed-by-sorted-string trick for the batched member and at-company lookups
  (`api/server.ts:171-232`) is a genuinely good piece of work: it turns one-request-per-row into one
  batched request, and the comment explains why the key is a string.
- **`initialData` from the server render** on events and announcements
  (`api/hooks/community.ts:31-39,138-146`) so lists paint on first byte and stay live for optimistic
  edits. Paths is the only screen that misses this.
- **Optimistic updates done properly**: snapshot, `cancelQueries`, rollback in `onError`, and for
  RSVP the server's authoritative row written back in `onSuccess` rather than a blind refetch. The
  per-row `mutation.variables?.id === row.id` busy check (`EventList.tsx:50`, `SaveButton.tsx:43`,
  `IntrosList.tsx:42`, `SavedList.tsx:86`) is the right way to keep one in-flight write from disabling
  a whole list.
- **`Toolbar.tsx:58-63`** is a textbook `client-passive-event-listeners` + `rerender-derived-state`
  compliance: `{ passive: true }`, cleanup, and it stores the derived boolean `window.scrollY > 8`
  rather than the continuous scroll value, so it re-renders on the transition and not per pixel.
- **`RelativeTime.tsx`** uses `useSyncExternalStore` with a server snapshot instead of the usual
  `useState` + `useEffect` hydration dance: one render on the server, one after hydration, no
  cascade. `Typewriter`'s `useReducedMotion` does the same.
- **Forms seed state from the server value at mount** instead of correcting it in an effect
  (`EntryForm.tsx:52-57`, `IntentsForm.tsx:29-35`, `HousingForm.tsx:62` with lazy `useState(() => seed(listing))`).
  `HousingForm` also gets `rerender-lazy-state-init` right.
- **`content-visibility: auto` on every long list** (`JobsBrowser.tsx:266`, `HousingBrowser.tsx:163`,
  `AskExplorer.tsx:194`, `PathsExplorer.tsx:175,206`): off-screen rows are not laid out.
- **`next/dynamic` with `ssr: false` for `PathsChart`** on both pages that draw it
  (`PathsExplorer.tsx:20-23`, `AskExplorer.tsx:22-25`), keeping the SVG maths out of the first load.
- **`api/client.ts` reads the token at request time** rather than capturing it, so a refresh reaches
  in-flight code, and `unwrap` parses the error envelope in exactly one place.
- **No inline component definitions, no index keys in reorderable lists, no prop mutation, no missing
  effect cleanup** anywhere in the live code. Those are the four failure modes that usually dominate a
  React audit of this size, and all four are clean.
