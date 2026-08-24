# Client-side render layer: implementation report (impl-fe2)

Scope: the files assigned to me. Another agent's server-data-flow edits landed in the same
tree while I worked; I did not touch their files. Verification at the end ran against the
combined tree.

## 1. Build blocker: `LoginForm.tsx` reading `picked?.email`: DONE

Confirmed at `src/app/login/LoginForm.tsx:94` (`if (picked?.email) setEmail(picked.email)`),
and confirmed against `backend/identity/api/dev_router.py`: `GET /auth/dev/members` returns
`DevMemberOption {id, slug, name, class_label}` and the docstring says outright that the reply
carries the slug and not the e-mail, because the route is unauthenticated. The slug is what
`POST /auth/dev/login` identifies the member by (`DevLoginRequest.member_slug`).

- `src/app/login/LoginForm.tsx`: the picker now just sets the member (`onSelect={setMember}`)
  and never writes the e-mail field. `submit` already passed `member?.slug`.
- `src/api/hooks/auth.ts`: `devLogin` now sends **one** identifier, the slug when there is one
  and the typed address otherwise. `DevLoginRequest` documents that passing both 409s when
  they name different people, which is exactly what would happen now that the picker cannot
  fill the address in for you. This is the one change outside the file the brief named; it is
  needed for "sign in as a roster member" to work at all, and `api/hooks/auth.ts` is not on
  the other agent's list.

`schema.d.ts` untouched. `npm run typecheck` now reports zero errors.

## 2. Logo SVG: DONE

`public/assets/cdtm.svg` was an Adobe Illustrator export: a DOCTYPE with eight entity
declarations, a `<switch>` whose first branch is a `<foreignObject requiredExtensions="&ns_ai;">`
holding a 1,166,376-character base64 `<i:pgf>` blob, and, after it, the real drawing (5
polygons, 2 paths, `viewBox="0 0 84.5 64"`, one fill `#134391`).

    npx --yes svgo --multipass --precision=1 -o <scratch>/cdtm.clean.svg public/assets/cdtm.svg
    1140.885 KiB - 99.9% = 0.787 KiB

SVGO kept the now-pointless `<switch>` and an empty `<foreignObject>`, so the file I shipped
is the SVGO output with those two removed and the `.st0` class replaced by a `fill` attribute
on the root (no `<style>` block to leak if the file is ever inlined). `viewBox` preserved, no
DTD, no entities, no `foreignObject`.

**Bytes: 1,168,266 -> 590 (-99.95%).**

Rendering checked, not eyeballed: `rsvg-convert` on the original and the replacement, then a
PIL difference histogram.

| render | pixels differing at all | max delta (0-255) |
| --- | --- | --- |
| 676x512 (16x the used size) | 664 of 346,112 (0.19%) | 74 |
| 43x32 (the size `AppShell`/`LoginForm` draw it at) | 37 of 1,376 (2.7%) | 7 |

All differences are edge antialiasing from `--precision=1` and SVGO's cubic-to-quadratic
folding. File name unchanged, both references (`AppShell.tsx:68`, `LoginForm.tsx:57`) still
resolve.

## 3. `lib/safeNext.ts` open redirect: DONE

Confirmed: the old body was `if (!value || !value.startsWith("/") || value.startsWith("//"))
return "/"`, and `new URL("/\\evil.example", origin)` resolves to `https://evil.example/`.

Now: reject anything not starting with `/`, reject `//` and `/\` openings (the two
two-character forms a browser reads as an authority), then parse against `http://n` and keep
the value only if `url.origin === "http://n"`, returning `url.pathname + url.search + url.hash`
so the caller gets what the parser saw. Doc comment kept and updated to say why string tests
alone are not enough. Checked in `scratchpad/safenext.mjs`:

    "/jobs" -> "/jobs"          "/jobs?a=1#x" -> "/jobs?a=1#x"    "/network?q=a%20b" -> unchanged
    "//evil.example" -> "/"     "/\evil.example" -> "/"           "/\\evil.example" -> "/"
    "\/evil" -> "/"             "https://evil.example" -> "/"     "javascript:alert(1)" -> "/"

## 4. `ImageUpload.tsx` multi-file upload: DONE

Confirmed at `src/components/ImageUpload.tsx:55-78`: the loop awaited each upload and then
called `onChange(multiple ? [...urls, result.url] : [result.url])` with the `urls` **prop**
from the render that started the loop, so three photos ended as one.

- URLs accumulate in a local `added: string[]`; one `onChange([...urls, ...added].slice(0, max))`
  after the loop (the `room` calculation already caps the selection, the slice is belt and
  braces). The misleading "Functional update" comment is gone, replaced by one that says why
  the accumulation is needed.
- Per-file progress still works and is now keyed by a stable id, `name:size:lastModified`
  (`fileId()`), used for the `setPending` map, the removal filter and the React `key`. Two
  files both called `IMG_0001.jpg` no longer drive each other's progress bar.

Rule: `rerender-functional-setstate` (the stale-closure half of it).

## 5. Search and filter state off the URL hot path: DONE

- `src/lib/urlState.ts`: `router.replace` is now inside `startTransition`, so every caller
  benefits. Doc comment extended to say why (`rerender-transitions`).
- `src/features/jobboard/JobsBrowser.tsx`: the search box is `useState` (immediate echo), the
  filter reads `useDeferredValue(typed)` (`rerender-use-deferred-value`), and the settled value
  is mirrored to the URL through the existing `useDebounced(typed, 300)` in an effect. The
  effect guards on a ref of what we last wrote, so a URL that changed some other way (back
  button) is left alone instead of being fought. "Clear everything" resets the local box as
  well as the params. Header comment updated: it used to claim every control writes to the
  address bar.
- `src/features/community/housing/HousingBrowser.tsx`: `kind` and `city` are now local state
  seeded from the URL, with `useCallback` setters that repaint immediately and then mirror to
  the URL (a transition, via `urlState`). Both filters are answered entirely from `listings`,
  which is already in memory.

Honest limitation, in the code comments too: with the box local, back/forward no longer
retypes the search text (the effect declines to overwrite the URL, but nothing pulls the URL
back into the box either). Adopting an externally-changed URL would need a setState during
render or in an effect; the latter is an eslint error in this repo (`react-hooks/set-state-in-effect`)
and the former can clobber characters typed while the debounce is in flight. Left as is.

## 6. Memoized rows and stable callbacks: DONE

- `AskExplorer.tsx`: `ResultRow` is `memo(function ResultRow(...))`; `onSelect` is a single
  `useCallback((id: string) => ...)` on the parent using the functional updater, and the row
  calls `onSelect(member.id)` instead of each row closing over its own selection state.
  `SelectedBar`'s `onClose` is a `useCallback` too. `whyMatched` is wrapped in `useMemo` keyed
  on `[member, filters]` (`filters` comes off the query cache, so its identity is stable).
- `JobRow.tsx`: `export default memo(JobRow)`.
- `HousingCard.tsx`: `export default memo(HousingCard)`.
- `CompanyPicker.tsx`: sorted options are `useMemo(() => (items ?? []).toSorted(byName), [items])`
  with `byName` at module scope, and the component is `memo`-wrapped.
- `SaveButton.tsx`: no more `.some()` per row. `api/hooks/me.ts` gains `useSavedIds()`, the
  same query with `select: savedIds` (a module-scope projection, so TanStack memoizes it per
  cache entry) returning `Set<string>`; the button does `saved.data?.has(memberId) ?? false`.
  `useMySaved` stays for `SavedList`, which wants the rows.

Rules: `rerender-memo`, `rerender-functional-setstate`, `js-set-map-lookups`,
`js-tosorted-immutable`.

Note on `memo` in a shared component: `JobRow` is also rendered from the server component
`app/(app)/page.tsx`. The Flight server unwraps `REACT_MEMO_TYPE` and renders the inner type
(`react-server-dom-turbopack-server.node.production.js`: `case REACT_MEMO_TYPE: return
renderElement(request, task, type.type, ...)`), so this is safe; the build confirms it.

## 7. `lib/format.ts`: DONE, output verified byte-identical

Confirmed: no cached `Intl` anywhere, three `toLocaleDateString`/`toLocaleString` calls per
event row and per housing card, a `new Intl.NumberFormat` per `formatPrice` call, and regex
literals inside `initials`, `slugify` and `paragraphs`.

- Module-scope formatters, one per option shape: `DATE`, `DATE_TIME`, `DAY`, `MONTH`,
  `WEEKDAY`, `DAY_MONTH`, `DAY_MONTH_YEAR`, `PLAIN_NUMBER`.
- Currency is a listing's own field, so `formatSalary` goes through a module-level
  `CURRENCY_FORMATS: Map<string, Intl.NumberFormat>` (`js-cache-function-results`).
- `dateRange` reads `new Date().getFullYear()` once per call and picks between the two
  hoisted formatters instead of building one.
- Regexes hoisted: `SPACE`, `LETTER` (`initials`, `firstName`), `COMBINING`, `NON_SLUG`,
  `SPACES`, `DASHES`, `EDGE_DASH` (`slugify`), `BLANK_LINE` (`paragraphs`):
  `js-hoist-regexp`. All the global ones are only used with `String.replace`, which resets
  `lastIndex`, and the script below calls each function repeatedly to prove it.

Equivalence check (`scratchpad/compare-format.mjs`, old file kept as `format.old.ts`, run
under `node --experimental-strip-types`): every exported function over 11 date strings
(including invalid/null/undefined), 8 names, 6 salary shapes, 7 prices, 6 room values, 7
slug inputs, 5 texts, 6 enum values, 5 date ranges, 6 URLs, 3 lists, plus repeated calls:

    checked 152 comparisons, 0 differences

## 8. `paths/layout.ts` O(L²): DONE, output verified identical

Confirmed at `:147-148` calling `totalFor` at `:216-229`: a `filter().reduce()` over the whole
link list, twice per link. Replaced by one pass building `sourceTotals` and `targetTotals`
`Map`s before the loop, then `get()` (`js-index-maps`). `totalFor` deleted. The source/target
key strings were already computed a few lines down, so they are now computed once and reused.

Equivalence check (`scratchpad/compare-layout.mjs`, baseline from `git show HEAD:`): a
realistic `PathFlowPublic` built from the four stages `PathsChart` draws (study, first_step,
current, intent; 8/7/8/5 groups) at three densities, plus the empty flow, a null-fields flow,
a link naming a node that does not exist, and a tie-count flow, each laid out at 880x470,
880x380 and 640x300, comparing `stages`, `nodes`, `links`, `width`, `height` and the full
`strands()` output:

    checked 21 layouts, 0 differences

Timing on the dense flow (152 links, the shape a full class filter produces):

    layout only, 2000 runs: old 1885.6 ms, new 904.9 ms      (2.1x)
    layout + strands, 400 runs: old 2066.8 ms, new 1443.6 ms

## 9. Rendering: DONE

- `components/MemberAvatar.tsx`: `decoding={priority ? "sync" : "async"}` with a comment
  explaining both halves. It was unconditional `sync`.
- `features/community/events/EventList.tsx`: `cv-row` added to the row `<li>`.
- `features/community/announcements/AnnouncementList.tsx`: the card `<li>` gets a new
  `cv-note` class. `cv-card`'s `contain-intrinsic-size: auto 320px` is a photo card's height,
  nothing like a collapsed announcement, so `globals.css` gains
  `.cv-note { content-visibility: auto; contain-intrinsic-size: auto 132px; }` next to the
  existing two, with a comment saying what 132px is.
- Container `[content-visibility:auto]` removed from `JobsBrowser.tsx` (the `<ul class="jlist">`),
  `HousingBrowser.tsx` (the `.hgrid`) and `AskExplorer.tsx` (the results `<ul>`), each with a
  one-line comment saying the rows carry it instead. Rows keep `cv-row` / `cv-card`.
- `HousingBrowser.tsx` passes `index` to `HousingCard`, which sets `priority={index < 2}` on
  its `next/image`.

Rule: `rendering-content-visibility`.

Not done, not mine: `src/app/(app)/directory/Client.tsx:77` still has
`[content-visibility:auto]` on a container `<ul>`. It is a new file from the other agent's
stream and was not in the brief's list. `PathsExplorer.tsx` (theirs) no longer contains the
attribute in the current tree.

## 10. `JobsBrowser` `shown` memo: DONE

Split into a `filtered` memo (`[pool, query, selection]`) and a `shown` memo
(`filtered.toSorted(COMPARATORS[sort])`, deps `[filtered, sort]`), with the four comparators
hoisted to a module-scope `COMPARATORS` record. Changing the sort no longer re-runs the
filter, the four closures are built once for the module, and the redundant `[...filtered]`
copy is gone. Rules: `rerender-split-combined-hooks`, `js-tosorted-immutable`.

## 11. Dead code: DONE (with one addition, flagged)

Grep across `src` (including the new `app/(app)/directory/*`) confirmed the six files form a
closed cluster: `MemberGrid.tsx` is imported by nothing and is the only importer of
`MemberTile.tsx`, `MemberModal.tsx`, `Toolbar.tsx`, `lib/profiles.ts` and `lib/types.ts`.
Deleted all six. `src/proxy.ts`'s matcher mentions `profiles` as a **public path** and
`public/profiles` is the loader's input; neither is affected.

`useMember` (`api/hooks/members.ts`) and `useJobs` (`api/hooks/jobboard.ts`): zero importers
(the directory now uses `api/hooks/directory.ts::useMemberSearch`; the board is server-loaded).

- `useJobs` removed from `jobboard.ts`, along with the now-unused `JobSearchParams` import; a
  line in the file's doc comment says why there is no `useJobs`.
- **`api/hooks/members.ts` was deleted entirely**, not just `useMember`. Removing its only
  export would have left a module whose five imports are all unused, which is a lint error.
  Nothing imports the module. Calling it out because it is a seventh deleted file, one the
  brief did not name.

`OnboardingForm.tsx`: the unused-disable warning was at `:89` in the current tree, not `:119`
(the other developer's edits moved it). Fixed by deleting the one
`// eslint-disable-next-line @next/next/no-img-element` line; the two comment lines above it
that explain why a plain `<img>` is used are kept.

Both `npm run lint` errors did live in `MemberGrid.tsx`; lint is now completely clean.

## 12. `api/keys.ts` housing keys: DONE

`housing: (params) => ["housing", "list", params]`, `housingListing: (id) => ["housing",
"detail", id]`, with a doc comment on the pair.

`api/hooks/community.ts` is not mine and is unchanged: its three housing mutations invalidate
`["housing"]`, which is still a prefix of both branches, so invalidation keeps working exactly
as before. Narrowing those three calls to `["housing", "list"]` (the actual win, since it no
longer throws away cached details on every write) is left for whoever owns that file.

## Verification

Run from `frontend/`, after all of the above, against the combined tree:

- `npm run typecheck`: **zero errors**. (Before: the two `TS2339` on `LoginForm.tsx:94`.)
- `npm run lint`: **completely clean**, no errors and no warnings. Earlier in the session it
  also reported `react/jsx-no-undef` for `PostedBy` and two unused imports in
  `app/(app)/jobs/[slug]/page.tsx`; that is the other agent's file and they cleared it while I
  worked. I did not touch it.
- `npm run build`: **passes**. First attempt hit "Another next build process is already
  running" (the other agent's build); retried after it finished.

```
▲ Next.js 16.3.1 (Turbopack)
✓ Compiled successfully in 2.8s
  Finished TypeScript in 5.5s
✓ Generating static pages using 9 workers (21/21) in 705ms

Route (app)
┌ ƒ /                        ├ ƒ /housing
├ ƒ /_not-found              ├ ƒ /housing/[id]
├ ƒ /announcements           ├ ƒ /housing/[id]/edit
├ ƒ /api/auth/dev-session    ├ ƒ /housing/new
├ ƒ /auth/callback           ├ ○ /icon.svg
├ ƒ /companies               ├ ƒ /jobs
├ ƒ /directory               ├ ƒ /jobs/[slug]
├ ƒ /events                  ├ ƒ /jobs/new
├ ƒ /events/[id]             ├ ƒ /login
├ ƒ /events/new              ├ ƒ /me
                             ├ ƒ /members/[slug]
                             ├ ƒ /network
                             ├ ƒ /onboarding
                             ├ ƒ /paths
                             └ ƒ /post

ƒ Proxy (Middleware)
○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

(The route table is one column in the real output; folded here to fit. 25 routes, all dynamic
except `/icon.svg`.)

## Files I touched

    public/assets/cdtm.svg                                   (rewritten, 1,168,266 -> 590 B)
    src/api/hooks/auth.ts                                    (item 1)
    src/api/hooks/jobboard.ts                                (item 11)
    src/api/hooks/me.ts                                      (item 6, one insertion)
    src/api/hooks/members.ts                                 DELETED (item 11)
    src/api/keys.ts                                          (item 12)
    src/app/globals.css                                      (item 9, .cv-note)
    src/app/login/LoginForm.tsx                              (item 1)
    src/app/onboarding/OnboardingForm.tsx                    (item 11, one line removed)
    src/components/ImageUpload.tsx                           (item 4)
    src/components/MemberAvatar.tsx                          (item 9)
    src/components/MemberGrid.tsx                            DELETED (item 11)
    src/components/MemberModal.tsx                           DELETED (item 11)
    src/components/MemberTile.tsx                            DELETED (item 11)
    src/components/Toolbar.tsx                               DELETED (item 11)
    src/features/community/SaveButton.tsx                    (item 6)
    src/features/community/announcements/AnnouncementList.tsx (items 7, 9)
    src/features/community/ask/AskExplorer.tsx               (items 6, 9)
    src/features/community/events/EventList.tsx              (item 9)
    src/features/community/housing/HousingBrowser.tsx        (items 5, 9)
    src/features/community/housing/HousingCard.tsx           (items 6, 9)
    src/features/community/paths/layout.ts                   (item 8)
    src/features/jobboard/CompanyPicker.tsx                  (item 6)
    src/features/jobboard/JobRow.tsx                         (item 6)
    src/features/jobboard/JobsBrowser.tsx                    (items 5, 6, 9, 10)
    src/lib/format.ts                                        (item 7)
    src/lib/profiles.ts                                      DELETED (item 11)
    src/lib/safeNext.ts                                      (item 3)
    src/lib/types.ts                                         DELETED (item 11)
    src/lib/urlState.ts                                      (item 5)

Nothing committed; no `git checkout`/`stash`/`reset` run. `public/avatars`, `public/profiles`,
`public/data` and `next.config.ts` untouched.

## Left undone

1. Back/forward does not restore the jobs search text or the housing filter chips any more
   (item 5, reasoned above).
2. `app/(app)/directory/Client.tsx:77` still has container-level `content-visibility` (item 9,
   not my file).
3. The three housing mutations in `api/hooks/community.ts` still invalidate the whole
   `["housing"]` root (item 12, not my file). Correct, just broader than it needs to be.
4. No browser run. The equivalence claims for `format.ts`, `layout.ts` and `safeNext.ts` are
   from node scripts against the pre-change code, and the SVG claim is from a rasteriser diff;
   the interaction claims (typing latency, chip responsiveness) are reasoned from the code and
   the rules, not measured in a browser.
