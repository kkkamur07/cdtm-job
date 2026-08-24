# Code review: CDTM Community platform (uncommitted working tree)

Five-axis review per `~/.claude/skills/code-review-and-quality/SKILL.md`. That skill has no
`references/` directory on this machine (`references/performance-checklist.md` and
`references/security-checklist.md` do not exist), so the performance and security axes below
follow the checklist embedded in `SKILL.md` itself plus the specific items named in the brief.

Baseline, and an important caveat about it. This review was started against the working tree as
it stood at the beginning of the session, when the whole application was uncommitted (2,392 files
staged, `communitytool/` and `jobboard/` pending deletion). While the review was in progress the
tree moved: three commits landed, and the working tree has been dirty and growing throughout.

```
f09b6df  Mark the platform as Beta in the masthead              <- HEAD
b938fe8  Add a name-first directory alongside Ask
37cbc23  Wire real Google auth, self-service profiles, and bulk community load
0654a34  fix                                                    <- session start
```

`git diff --shortstat 0654a34..HEAD` is `3010 files changed, 79593 insertions(+), 19484
deletions(-)`, and `git diff --shortstat` on top of that was 6 files when I began re-checking and
9 files a few minutes later:

```
 M backend/members/api/me.py                    M frontend/openapi/openapi.json
 M backend/members/application/commands.py      M frontend/src/api/schema.d.ts
 M backend/members/application/member_service.py    M tests/integration/test_identity_gaps.py
 M backend/members/application/ports.py         M tests/unit/test_media_gaps.py
 M backend/members/infrastructure/members_repository.py
```

Because the brief asks for the current state of the code rather than a diff, this matters less
than it might, but two things follow and both are stated honestly rather than papered over:

1. **Every finding below was re-verified against the tree at `f09b6df` plus those modifications**,
   after I noticed the tree had moved. All four blocking findings still reproduce at the same
   file and line, and both quality gates still fail identically. The verification output in the
   next section was re-run at that point.
2. **The tree is being edited while it is being reviewed.** Anything I did not re-check in the
   last pass could have changed underneath the review. The in-flight work is the self-service
   profile edit path, noted at the end of the Correctness section.

No secrets were found in any reviewed file. `frontend/src/lib/supabase/env.ts` reads only
`NEXT_PUBLIC_*` values and says so; the service-role key never appears outside
`backend/media/infrastructure/supabase_storage.py`, which receives it from settings.

---

## Verification

### `uv run poe test-fast` (verbatim tail)

Re-run against the current tree, after I found that the tree had moved during the review:

```
........................................................................ [ 44%]
........................................................................ [ 58%]
........................................................................ [ 73%]
........................................................................ [ 88%]
.........................................................                [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/krishuagarwal/Desktop/Programming/python/cdtm-job/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
488 passed, 1 skipped, 230 deselected, 1 warning in 12.92s
EXIT=0
```

Earlier in the session the same command reported `451 passed, 1 skipped, 216 deselected`. The
suite grew by 37 tests while the review was running and stayed green, which is a good sign about
the work in flight, though none of the new tests cover `update_profile` (see the Correctness
section).

### `cd frontend && npm run typecheck` (verbatim)

```
> cdtm-community@0.1.0 typecheck
> tsc --noEmit

src/app/login/LoginForm.tsx(94,49): error TS2339: Property 'email' does not exist on type '{ class_label?: string | null | undefined; id: string; name: string; slug: string; }'.
src/app/login/LoginForm.tsx(94,72): error TS2339: Property 'email' does not exist on type '{ class_label?: string | null | undefined; id: string; name: string; slug: string; }'.
EXIT=2
```

### `cd frontend && npm run lint` (verbatim)

```
> cdtm-community@0.1.0 lint
> eslint


/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/app/onboarding/OnboardingForm.tsx
  119:21  warning  Unused eslint-disable directive (no problems were reported from '@next/next/no-img-element')

/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/components/MemberGrid.tsx
   98:21  error  Error: Calling setState synchronously within an effect can trigger cascading renders

Effects are intended to synchronize state between React and external systems such as manually updating the DOM, state management libraries, or other platform APIs. In general, the body of an effect should do one or both of the following:
* Update external systems with the latest state from React.
* Subscribe for updates from some external system, calling setState in a callback function when external state changes.

Calling setState synchronously within an effect body causes cascading renders that can hurt performance, and is not recommended. (https://react.dev/learn/you-might-not-need-an-effect).

/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/components/MemberGrid.tsx:98:21
   96 |     }, [query, filterWith]);
   97 |
>  98 |     useEffect(() => setLimit(PAGE), [applied, classId, role]);
      |                     ^^^^^^^^ Avoid calling setState() directly within an effect
   99 |
  100 |     // Selection lives in the URL, so profiles are linkable and the browser back
  101 |     // button closes the modal: which people expect and otherwise complain about  react-hooks/set-state-in-effect
  138:13  error  Error: Calling setState synchronously within an effect can trigger cascading renders

Effects are intended to synchronize state between React and external systems such as manually updating the DOM, state management libraries, or other platform APIs. In general, the body of an effect should do one or both of the following:
* Update external systems with the latest state from React.
* Subscribe for updates from some external system, calling setState in a callback function when external state changes.

Calling setState synchronously within an effect body causes cascading renders that can hurt performance, and is not recommended. (https://react.dev/learn/you-might-not-need-an-effect).

/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/components/MemberGrid.tsx:138:13
  136 |     useEffect(() => {
  137 |         if (!selectedId) {
> 138 |             setProfile(null);
      |             ^^^^^^^^^^ Avoid calling setState() directly within an effect
  139 |             return;
  140 |         }
  141 |         let cancelled = false;                                                                                                                          react-hooks/set-state-in-effect
```

```
✖ 3 problems (2 errors, 1 warning)
  0 errors and 1 warning potentially fixable with the `--fix` option.

EXIT=1
```

### Measured evidence (runtime harness)

The performance findings below are not read off the source alone. I ran the API against the
project's configured Postgres (a hosted `<redacted>.pooler.supabase.com`, so every statement is a
real network round trip, which is the production topology) with `echo=True`, and counted the SQL
each endpoint issues after two warm-up calls. Raw traces are in the scratchpad under
`echo-slices/`, timings in `timings.psv`, statement counts in `counts.psv`, and per-route API
call counts in `dev-signedin.psv`.

Statements per request, after warm-up (`counts.psv`, columns: SQL statements | transaction
markers | total | status):

```
GET-members-limit60|12|4|16|200      GET-jobs|5|4|9|200
GET-members-q|12|4|16|200            GET-companies-100|2|2|4|200
GET-members-facets|6|4|10|200        GET-housing|5|4|9|200
GET-members-slug|11|4|15|200         GET-events-upcoming100|5|4|9|200
GET-paths-flow|10|4|14|200           GET-announcements-50|6|4|10|200
GET-paths-groups|6|4|10|200          GET-auth-me|4|4|8|200
GET-paths-members|6|4|10|200         GET-network-saved|4|4|8|200
GET-members-at-company|12|4|16|200
```

Wall time, median of five, same host (`timings.psv`):

```
GET /health (baseline, no DB)          0.351s
GET /companies/?limit=100              0.462s
GET /auth/me                           0.964s
GET /announcements/?limit=50           1.124s
GET /members/?limit=60                 1.815s
```

Note: `GET-members-lookup50` returned 422 in this harness (the id list exceeded the documented
cap of 50), so that row measures the rejection path and is not cited anywhere below.

Summary: backend green, frontend red on both gates.

---

## 1. Correctness

### Critical: the frontend does not typecheck, so it does not build

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/app/login/LoginForm.tsx:94`

**Evidence:** `error TS2339: Property 'email' does not exist on type '{ class_label?: string | null | undefined; id: string; name: string; slug: string; }'` (twice, columns 49 and 72). The type is `DevMemberOption` from the generated `src/api/schema.d.ts`, reached through `frontend/src/auth/contract.ts:10`:

```ts
export type DevMember = components["schemas"]["DevMemberOption"];
```

**Why it matters:** `next build` runs the same type check by default, so this is a broken build, not a lint nit. The backend's `DevMemberOption` never carried `email`, and the code reads it anyway. Whatever the login picker renders on that line is `undefined` at runtime.

**Fix:** Either drop the `email` reads from the picker, or add `email` to `DevMemberOption` in the backend, re-run `uv run poe openapi` and `npm run generate:api`, and commit both. Do not cast around it.

### Critical: uploading several images at once keeps only the last one

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/components/ImageUpload.tsx:55-78`

**Evidence:**

```ts
for (const file of chosen) {
    ...
    const result = await uploadMedia(kind, file, token, ...);
    // Functional update: several uploads finish independently.
    onChange(multiple ? [...urls, result.url] : [result.url]);
```

**Why it matters:** `urls` is a prop captured when `accept` was created (`useCallback(..., [kind, max, multiple, onChange, token, urls])` at line 82). It does not change between iterations of this loop. Dropping three photos on a housing listing therefore calls `onChange([...urls, A])`, then `onChange([...urls, B])`, then `onChange([...urls, C])`; the form ends up with `urls + C` and photos A and B are silently lost, having already consumed bandwidth and a bucket object. The comment on line 71 asserts a functional update that the code does not perform. The `max` accounting on line 49 is computed from the same stale `urls`, so the cap is also wrong for a multi-file drop.

**Fix:** Accumulate locally and call `onChange` once, or make `onChange` accept an updater. For example collect `const added: string[] = []` inside the loop, push each `result.url`, and call `onChange(multiple ? [...urls, ...added] : added.slice(-1))` after the loop, recomputing `room` against `urls.length + added.length`.

### `loadCompanyMap()` truncates at 100 companies, so jobs beyond that lose their company

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/api/server.ts:155-158`, consumed at `frontend/src/app/(app)/jobs/[slug]/page.tsx:46,55-56`

**Evidence:**

```ts
export const loadCompanyMap = cache(async (): Promise<Map<string, Company>> => {
    const companies = await loadCompanies({ limit: 100 });
    return new Map(companies.items.map((company) => [company.id, company]));
});
```

and

```ts
const company = job.company_id ? companies?.get(job.company_id) : undefined;
const name = company?.name ?? "A CDTM company";
```

**Why it matters:** 100 is the hard cap in `backend/core/api/pagination.py:17` (`limit: Annotated[int, Query(ge=1, le=100)]`), so this is the whole page and there is no second page. Company number 101 onwards will render every one of its jobs as "A CDTM company" with no logo and no link, and the failure is silent. This only appears once the company table passes 100 rows, which is exactly the load condition the brief asks about.

**Fix:** On the job detail page the job already carries `company_id`, so call `loadCompany(job.company_id)` instead of building a map (the home page already does this, see the next finding). Where a map is genuinely needed, page through until `items.length === total` or resolve the ids the page actually shows.

### The job board's result count is wrong past 100 listings

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/app/(app)/jobs/page.tsx:30,86` and `frontend/src/features/jobboard/JobsBrowser.tsx:257-261`

**Evidence:**

```ts
loadJobs({ status: "published", limit: 100 }),
...
<JobsBrowser jobs={rows} total={jobs.total} />
```

```tsx
<b className="tabular-nums text-ink">{shown.length}</b> of {total}{" "}
{total === 1 ? "listing" : "listings"}
```

**Why it matters:** `jobs` holds at most 100 rows while `total` is the server's full count. With 250 published jobs the board says "Showing 100 of 250 listings" and offers no way to reach the other 150; every facet count in the sidebar is also computed over the truncated pool (`JobsBrowser.tsx:91-103`). The comment at `JobsBrowser.tsx:44-45` acknowledges the design limit ("If the board ever outgrows a hundred listings this moves back to the API's own query parameters") but nothing detects or reports the moment it does.

**Fix:** Either pass the truncated count as the denominator, or add a visible "showing the first 100 of N" line. Longer term, move filtering to the API query parameters as the comment intends.

### Nit: upload progress is keyed by file name, so same-named files collide

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/components/ImageUpload.tsx:62,66-69,76,129`

**Evidence:** `current.map((item) => item.name === file.name ? { ...item, percent } : item)` and `key={item.name}`.

**Why it matters:** Two files called `IMG_0001.jpg` from different folders share a progress bar, and the `finally` filter at line 76 removes both when the first finishes. React also warns on duplicate keys.

**Fix:** Key the pending list on a per-upload id (a counter or `crypto.randomUUID()`), keeping the file name only as the label.

### FYI: the backend's correctness story is well covered

`uv run poe test-fast` is green at 488 passing, and the tests do exercise the behaviours the brief asked about:
`tests/unit/test_members_service_gaps.py:35` (`test_lookup_resolves_at_most_fifty_ids_and_collapses_duplicates`),
`tests/unit/test_members_service_gaps.py` (`test_contacts_at_asks_about_at_most_fifty_companies`),
`tests/integration/test_ask.py:170` (`test_asking_faster_than_the_limit_is_a_429`, which also asserts `/ask/explain` shares the bucket),
`tests/integration/test_media.py:79` (`test_oversize_upload_is_413`),
`tests/integration/test_members_b_gaps.py:327,397` (lookup ordering and directory facets).

I also confirmed empirically that `Query(max_length=50)` on `list[UUID]` / `list[str]` constrains the list length rather than each element, so the batch caps in `backend/members/api/members.py:70-109` really do hold:

```
lookup 200 ids -> 422 {"detail":[{"type":"too_long","loc":["query","ids"],"msg":"List should have at most 50 items after validation, not 200", ...
at-company 200 names -> 422 {"detail":[{"type":"too_long","loc":["query","company"], ...
```

### FYI: the profile-edit path is in flight and currently untested

**Location:** `backend/members/infrastructure/members_repository.py:334-389` (`update_profile`),
`backend/members/application/member_service.py:135`, `backend/members/application/ports.py:78-93`,
`backend/members/api/me.py`, all uncommitted at the time of review.

**Evidence:** `grep -rn "update_profile" tests/` returns nothing. The only caller is
`member_service.py:135`.

**Why it matters:** This is a write path that mutates member-owned data and rewrites
`search_text`, added after the suite around it was written, so `uv run poe test-fast` being green
says nothing about it. It is not a defect and I am not blocking on it, but it should not merge
without a test: the repository method has a real invariant worth pinning, stated in its own
docstring, that an edit must not destroy positions and educations the way `upsert_member` does.

Two things I checked and found fine, so they are not findings: committing inside the repository
is the established convention here (all twelve repositories do it), and the deliberate omission of
slug, avatar and e-mail from the argument list is correct and well argued in the docstring.

**Fix:** Add a unit test asserting that `update_profile` leaves positions and educations intact and
that class membership is replaced rather than appended.

---

## 2. Readability and simplicity

### Dead code: an orphaned island of about 800 lines from the previous app

**Location:** `frontend/src/components/MemberGrid.tsx` (220), `frontend/src/components/MemberTile.tsx` (97),
`frontend/src/components/MemberModal.tsx` (254), `frontend/src/components/Toolbar.tsx` (203),
`frontend/src/lib/types.ts` (120), `frontend/src/lib/profiles.ts` (67)

**Evidence:** Nothing outside this cluster imports `MemberGrid`. A repository-wide search for importers returns:

```
MemberGrid    : (nothing)
MemberTile    : components/MemberGrid.tsx
MemberModal   : components/MemberGrid.tsx
Toolbar       : components/MemberGrid.tsx
```

and the only importers of `@/lib/types` and `@/lib/profiles` are those same four files. They use the old camelCase shape (`m.classLabel`, `m.isCA`, `m.roles`) from `lib/types.ts`, not `@/api/types`, and fetch `/profiles/${id}.json` directly (`lib/profiles.ts:23`) rather than going through the API client. `frontend/src/features/community/members/` is the live replacement.

**Why it matters:** Both lint errors in this change live in `MemberGrid.tsx`, so a red quality gate is being paid for code nothing renders. It also actively misleads: a reader looking for the directory grid finds two of them, one of which reads a data source `docs/architecture.md` says is offline-only ("Nothing in the request path reads them").

**Fix:** Per the skill's dead-code hygiene rule, this is a "list it and ask" case rather than a silent delete. Confirm with the author, then remove all six files. That also clears both lint errors.

### `rate_limit_key` is written out three times, identically

**Location:** `backend/members/application/ask_service.py:212-219`, `backend/housing/application/housing_ask_service.py:166-173`, `backend/jobboard/application/job_ask_service.py:170-178`

**Evidence:** All three end in `return str(actor.member_id) if actor.member_id else "unbound"`, and each carries a docstring explaining that it must be spelled the same way as the other two.

**Why it matters:** The docstrings themselves are the argument for extracting it: three copies whose whole contract is "these must agree" is exactly the shape that drifts. `Actor` already lives in `backend/core/actor.py`, and the shared Ask machinery already lives in `backend/core/llm/`, so there is a home for it that breaks no context boundary.

**Fix:** Move it to `backend/core/llm/ask.py` next to `validate_question`, or to `backend/core/actor.py`, and import it from the three services.

### Consider: two spellings of the same read, in `api/server.ts` and `api/hooks/`

**Location:** `frontend/src/api/server.ts:93-98` versus `frontend/src/api/hooks/community.ts:36,143`

**Evidence:**

```ts
export const loadAnnouncements = cache(() =>
    get<Page<Announcement> & { unread: number }>("/announcements/", { limit: 50 }),
);
export const loadEvents = cache((upcoming: boolean) =>
    get<Page<CommunityEvent>>("/events/", { upcoming, limit: 100 }),
);
```

```ts
unwrap(api.GET("/api/v1/events/", { params: { query: { upcoming, limit: 100 } } })),
...
unwrap(api.GET("/api/v1/announcements/", { params: { query: { limit: 50 } } })),
```

**Why it matters:** The server loader and the client hook must agree on the page size, because the hook takes the loader's result as `initialData` (`community.ts:38,146`). Today they agree by coincidence of two literals in two files. Changing one is a silent cache mismatch, not a compile error.

**Fix:** Export the limits from one module (`api/keys.ts` or a small `api/limits.ts`) and have both sides import them.

### Nit: files over 250 lines

Measured with `wc -l` over `frontend/src`, excluding the generated `schema.d.ts`:

| Lines | File | Should it split? |
|---|---|---|
| 304 | `features/community/ask/AskExplorer.tsx` | Probably; it is a screen, not a component. |
| 300 | `lib/format.ts` | No. It is a flat list of independent pure helpers, which is the readable shape. |
| 297 | `app/(app)/housing/[id]/page.tsx` | Yes. It holds three async server sub-components (`MembersInCity:205`, `AlsoInCity:240`) plus `daysLeft:292`; the two panels belong in `features/community/housing/`. |
| 295 | `features/jobboard/JobsBrowser.tsx` | Yes. The facet sidebar is a self-contained component. |
| 295 | `app/(app)/jobs/new/Client.tsx` | Yes, a form this long usually splits by section. |
| 293 | `app/onboarding/OnboardingForm.tsx` | Same. |
| 291 | `api/hooks/community.ts` | Yes. It is three unrelated boards (events, announcements, housing) plus paths in one file, and the boards are separate bounded contexts. |
| 290 | `features/community/paths/PathsChart.tsx` | Borderline; `Node` at line 160 could move out. |
| 274 | `features/community/members/MemberProfileView.tsx` | Borderline. |
| 264 | `app/(app)/jobs/[slug]/page.tsx` | Yes, `PeopleAtCompany:234` belongs in `features/jobboard/`. |
| 254 | `components/MemberModal.tsx` | Delete it; see the dead-code finding. |

Backend equivalents are mostly rule tables (`ask_translator_rules.py` at 425, `paths_classifier.py` at 338) where length is data, not complexity. `backend/core/app.py` at 307 is the one worth watching.

---

## 3. Architecture

### The frontend reintroduces "community" as a context name, which the domain language forbids

**Location:** `frontend/src/features/community/` (subdirectories `announcements`, `ask`, `events`, `home`, `housing`, `me`, `members`, `paths`)

**Evidence:** `CONTEXT-MAP.md`, section "Words nobody may use":

> "Community" as the name of a context. It was the name of one package that held six boards; now it is only the name of the product.

and `docs/architecture.md` section 3:

> Until 2026-08-22 the six contexts in the middle were one package called `community`. ... Nothing called `backend/community/` or `/api/v1/community/...` exists any more.

The frontend then groups members, network (`me/SavedList.tsx`, `me/IntrosList.tsx`), paths, events, announcements and housing under exactly that name.

**Why it matters:** ADR 0007 split the backend along the product's boards specifically so that the six aggregates stopped sharing a vocabulary. The frontend slices are the place a reader looks to find the UI for a context, and today `features/community/` recreates the package the ADR removed, one layer up. The mismatch also makes the mapping from a backend context to its UI non-obvious: `network` has no slice of its own and lives inside `me/`.

**Fix:** Flatten to one slice per bounded context: `features/members/`, `features/network/`, `features/paths/`, `features/events/`, `features/announcements/`, `features/housing/`, `features/jobboard/`. This is a directory move, not a rewrite.

### The shared Ask UI is nested inside one board's slice and imported by another

**Location:** `frontend/src/features/community/ask/` imported from `frontend/src/features/jobboard/JobsBrowser.tsx:8-10`

**Evidence:**

```ts
import AskAnalysis from "@/features/community/ask/AskAnalysis";
import AskLine from "@/features/community/ask/AskLine";
import { useJobAsk } from "@/features/community/ask/useAsk";
```

`frontend/src/features/community/housing/HousingBrowser.tsx` imports the same three.

**Why it matters:** The backend puts exactly this shared machinery in `core` (`backend/core/llm/ask.py`, and `docs/architecture.md` lists "the shared Ask machinery and `ask_quota`" under `core`). The frontend puts it inside one board and then has two other boards reach into it, which is the coupling the layout is meant to prevent. `useAsk.ts` even holds all three boards' hooks (`useAsk`, `useJobAsk`, `useHousingAsk`) in one file, so it is plainly shared code.

**Fix:** Promote it to `frontend/src/features/ask/` (or `src/components/ask/`), mirroring `backend/core/llm/`.

### A router imports from its own `infrastructure/` instead of going through `api/deps.py`

**Location:** `backend/housing/api/ask.py:16,48`

**Evidence:**

```py
from backend.housing.infrastructure.housing_ask_translator_rules import DISTRICTS
...
districts=sorted(set(DISTRICTS.values())),
```

**Why it matters:** Every other context's `api/` reaches infrastructure only through `api/deps.py` (verified: `announcements/api/deps.py`, `events/api/deps.py`, `jobboard/api/deps.py`, `members/api/deps.py`, `network/api/deps.py`, `paths/api/deps.py`, `identity/api/deps.py`, `housing/api/deps.py` are the only such importers, plus `media/api/router.py` which has no `deps.py`). `housing/api/ask.py` is the single router module that reaches past it. `DISTRICTS` is a vocabulary list the API publishes to the UI, so it is arguably domain data sitting in the wrong layer.

**Fix:** Move `DISTRICTS` to `backend/housing/domain/`, where the translator can also read it, or expose it through `housing/api/deps.py`.

### FYI: the layering rules that were checked and hold

- **No repository is imported by a router.** Every repository import in `backend/*/api/` is in a `deps.py`, which `AGENTS.md` defines as the DI wiring half of the `api/` layer. `backend/media/api/router.py:25` imports `get_blob_storage` directly, but `media` has no aggregate and no `deps.py`, which the module docstring states.
- **No domain model imports SQLAlchemy or FastAPI.** `grep -rn 'sqlalchemy\|fastapi' backend/*/domain/*.py` returns nothing.
- **Cross-context imports are confined to the documented exception.** The only ones are `backend/members/api/{ask,deps,schemas}.py` importing `backend.paths.*`, which is the composition seam `docs/architecture.md` section 3 explicitly allows. Note that it reaches `paths.application.ports` and `paths.domain` and not only `paths.api`, which is a slightly wider seam than "compose two contexts into one response" describes; worth one sentence in the architecture doc rather than a code change.

---

## 4. Security

### Critical: `safeNext` is bypassable with a backslash, giving an open redirect on the sign-in screen

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/lib/safeNext.ts:10-13`, used at `frontend/src/app/login/LoginForm.tsx:26,35,51`

**Evidence:**

```ts
export function safeNext(value: string | null | undefined): string {
    if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
    return value;
}
```

The guard rejects `//evil.example` but not `/\evil.example`. Verified with Node's WHATWG URL parser, which treats `\` as `/` for special schemes:

```
"/\\evil.example"  -> safeNext: "/\\evil.example" -> resolves to: https://evil.example/
"/\\/evil.example" -> safeNext: "/\\/evil.example" -> resolves to: https://evil.example/
"//evil.example"   -> safeNext: "/"               -> resolves to: https://app.cdtm.com/
```

`LoginForm.tsx` then hands that value straight to the router:

```tsx
useEffect(() => {
    if (signedIn) router.replace(next);
}, [signedIn, next, router]);
...
else router.replace(next);
```

**Why it matters:** The file's own docstring states the threat ("both are a phishing tool if they will bounce to another origin on the strength of it") and the check does not cover it. `/login?next=/\evil.example` is a link on the real CDTM origin that lands a member on an attacker's page immediately after a successful sign-in, which is the highest-trust moment in the flow.

Note that `frontend/src/app/auth/callback/route.ts:38` is safe today only by accident: it does `NextResponse.redirect(`${origin}${next}`)`, and string-concatenating before parsing yields `https://app.cdtm.com//evil.example`, a same-origin path. That is one refactor away from being an open redirect too, and it should not be relied on.

**Fix:** Resolve and compare rather than pattern-match. For example:

```ts
export function safeNext(value: string | null | undefined): string {
    if (!value) return "/";
    try {
        const base = "https://cdtm.invalid";
        const url = new URL(value, base);
        if (url.origin !== base) return "/";
        return `${url.pathname}${url.search}${url.hash}`;
    } catch {
        return "/";
    }
}
```

Add a unit test with `//evil`, `/\evil`, `/\/evil`, `https://evil`, `javascript:alert(1)` and a valid `/members/x?y=1#z`.

### `/members/at-company` accepts company names of unbounded length

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/backend/members/api/members.py:89-99`

**Evidence:**

```py
company: Annotated[
    list[str],
    Query(
        max_length=50,
        description="repeatable company name; one member is returned for each",
    ),
],
```

`max_length=50` constrains the number of names (verified above), not each name. The sibling endpoint at line 39 does constrain the value: `company: Annotated[str | None, Query(max_length=128)]`.

**Why it matters:** Each name becomes an `ILIKE '%...%'` pattern against `members.current_company` and the denormalised `members.search_text` through a LATERAL join (`backend/members/infrastructure/members_repository.py:141-158`). Fifty very long patterns is fifty expensive scans on a column with no index for that shape, from a single authenticated request. It is not injection (the pattern is bound as a column value and `backend/core/sql.py:6-9` escapes `%` and `_`), it is an unmetered cost. The same applies to `/paths/flow`, where `study_group`, `first_step_group` and `current_group` carry no `max_length` at all (`backend/paths/api/paths.py:41-43`) while the sibling `/paths/members` does (`group: Annotated[str, Query(max_length=120)]`, line 61).

**Fix:** Add `Query(max_length=128)` to each item, for example `list[Annotated[str, StringConstraints(max_length=128)]]`, and give the three `/paths/flow` group parameters the same 120 the members endpoint uses.

### Consider: `script-src 'unsafe-inline'` ships to production

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/next.config.ts:92`

**Evidence:**

```ts
`script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
```

with a thorough justification at lines 74-89.

**Why it matters:** `'unsafe-inline'` on `script-src` removes most of what CSP buys against XSS. The justification is honest and the alternatives are correctly described, but it is worth recording that the mitigation is "nothing in this app renders untrusted HTML" rather than the CSP itself. The one place member-supplied text becomes an attribute is `frontend/src/lib/format.ts:234-242` (`safeUrl`), and that is correct: it allow-lists `http:`, `https:` and `mailto:` and returns `null` otherwise, so `javascript:` hrefs cannot reach the DOM.

**Fix:** No change required now. Next 16 does support a per-request nonce from `src/proxy.ts`, so the "cannot be expressed" part of the comment is slightly stronger than the facts; consider softening the comment to "not worth forcing every route dynamic for" and filing it.

### FYI: the parts of the request path that are correct

- **Personalised responses are never cached.** `frontend/src/api/server.ts:56-63`: `...(accessToken || options?.revalidate === undefined ? { cache: "no-store" } : { next: { revalidate: options.revalidate } })`. Any request carrying a bearer token takes `no-store`, so no member's data can land in a shared Data Cache entry. This is the right shape.
- **Token forwarding.** `frontend/src/api/server.ts:52-54` reads the token from the request's own cookies through `getAccessToken()` on every call and holds nothing at module scope; `frontend/src/lib/supabase/server.ts:63-81` authorises on `getClaims()` (signature-verified) and uses `getSession()` only to recover the raw string to forward. `frontend/src/api/client.ts:25-36` keeps a module-level token but is browser-only and reads it at request time inside the middleware, so a refresh reaches in-flight requests rather than a captured stale value.
- **Media upload validation.** `backend/media/api/router.py:92-103` reads `limit + 1` bytes and 413s past the limit before holding an unbounded body, then ignores the declared content type and sniffs magic bytes (`backend/media/infrastructure/images.py:26-39`). Keys are `<uuid4>.<ext>` matched against `_KEY_RE` (line 23), and `LocalDiskStorage.path_for` (`local_disk.py:27-40`) re-checks that the resolved parent is the bucket directory. Blocking file IO runs on `anyio.to_thread`. This is a well-built boundary.
- **SQL is parameterised throughout.** The one dynamic fragment, `backend/members/infrastructure/_member_query.py:49-54`, interpolates a column name chosen from the fixed `_PATH_GROUP_COLUMNS` dict and binds the value, so the `noqa: S608` is justified.

---

## 5. Performance

### Every authenticated request writes to `accounts` and commits

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/backend/identity/infrastructure/account_repository.py:58-88`, reached from `backend/identity/application/auth_service.py:64` on every call to `authenticate`

**Evidence:**

```py
row = await self._s.scalar(select(AccountRow).where(AccountRow.auth_user_id == claims.sub))
now = utc_now()
if row is None:
    ...
else:
    row.email = claims.email
    ...
    row.last_sign_in_at = now
    row.updated_at = now
await self._s.commit()
await self._s.refresh(row)
```

`get_optional_principal` (`backend/identity/api/deps.py:88-95`) runs for every `PrincipalDep`, `ActorDep` and `OptionalActorDep`, which is every route in the app.

**Why it matters:** `last_sign_in_at` and `updated_at` are assigned unconditionally, so the UPDATE always fires. A plain `GET /members/?q=x` therefore costs a SELECT, an UPDATE, a COMMIT and a REFRESH SELECT against `accounts` before the search runs: four round trips of pure overhead. Worse under concurrency: `frontend/src/app/(app)/page.tsx:47-56` fires eight loaders in one `Promise.all`, and `frontend/src/app/(app)/layout.tsx:17-21` three more, so a single home-page render opens up to eleven concurrent write transactions all updating the same `accounts` row. They serialise on that row lock. The field is called `last_sign_in_at`, which suggests the write was meant for sign-in, not for every read. `docs/architecture.md` step 4 does describe this as intended, so this is a deliberate design to revisit rather than an oversight.

**Measured.** `GET /auth/me`, an endpoint whose entire job is to echo the caller back, issues
four statements across two transactions (`echo-slices/GET-auth-me.txt`):

```
BEGIN (implicit)
SELECT accounts.id, accounts.auth_user_id, accounts.email, ...
UPDATE accounts SET last_sign_in_at=...
COMMIT
BEGIN (implicit)
SELECT accounts.id, accounts.auth_user_id, accounts.email, ...
ROLLBACK
```

Compare `GET /companies/?limit=100`, which takes no principal: two statements, one transaction,
no write (`echo-slices/GET-companies-100.txt`). So the authentication prelude costs three
statements and a committed write transaction on every authenticated request, and the accounts row
is read twice. In wall time on this host that is `/health` at 0.351s against `/auth/me` at 0.964s.
Every one of the 13 API calls the home page makes pays it (see `dev-signedin.psv`), all writing
the same row.

**Fix:** Only write when something actually changed, and treat `last_sign_in_at` as coarse. For example skip the assignment when `row.last_sign_in_at` is within the last N minutes and no claim differs, and return early without `commit()`/`refresh()` when the row is unmodified (`self._s.is_modified(row)` or an explicit dirty check). That turns the common case into one SELECT.

### The directory search loads six relationships it does not use

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/backend/members/infrastructure/orm_models.py:88-111`, used by `backend/members/infrastructure/members_repository.py:50-67` and `:113-124`

**Evidence:** All six relationships are eager:

```py
classes: Mapped[list[ClassRow]] = relationship(secondary="member_classes", lazy="selectin", ...)
positions: Mapped[list[PositionRow]] = relationship(..., lazy="selectin", ...)
educations: Mapped[list[EducationRow]] = relationship(..., lazy="selectin", ...)
ca_detail: Mapped[CaDetailRow | None] = relationship(..., lazy="selectin", uselist=False)
entry: Mapped[MemberEntryRow | None] = relationship(..., lazy="selectin", uselist=False)
intents: Mapped[MemberIntentsRow | None] = relationship(..., lazy="selectin", uselist=False)
```

`search()` builds `apply_member_filters(select(MemberRow), filters)` with no loader options, and a repository-wide search for `selectinload`, `raiseload`, `noload`, `lazyload`, `defer(` or `load_only` returns nothing. The card it produces, `to_member` in `backend/members/infrastructure/_mappers.py:32-55`, reads only `row.classes`, `row.entry` and `row.intents`. `positions`, `educations` and `ca_detail` are read only by `to_profile` (lines 68-73), which `search` never calls.

**Why it matters:** `lazy="selectin"` is the relationship's default strategy, so it applies to every query that returns `MemberRow` entities. A directory page at `limit=100` therefore issues one main SELECT plus six `WHERE id IN (...)` SELECTs plus the `_claimed_ids` query (line 69-75): eight round trips where four would do. The two wasted ones are the largest tables: with a LinkedIn scrape behind them, 100 members means roughly 500 to 1,000 `PositionRow` and `EducationRow` objects hydrated into Python, mapped, and thrown away on every single search and every `/members/lookup` batch of 50. This is the hottest read in the product.

**Fix:** Flip the three profile-only relationships to `lazy="raise"` or `lazy="select"` on the model and add explicit `.options(selectinload(MemberRow.positions), selectinload(MemberRow.educations), selectinload(MemberRow.ca_detail))` to `get_by_slug` and `get_by_id` only. Alternatively keep `selectin` as the default and add `.options(noload(MemberRow.positions), noload(MemberRow.educations), noload(MemberRow.ca_detail))` to `search` and `get_many`. **Measured.** `GET /members/?limit=60` issues 12 statements
(`echo-slices/GET-members-limit60.txt`), in this order:

```
 1  BEGIN (implicit)
 2  SELECT accounts...              <- auth prelude
 3  UPDATE accounts SET last_sign_in_at=
 4  COMMIT
 5  BEGIN (implicit)
 6  SELECT accounts...              <- auth prelude, second read
 7  SELECT count(*)                 <- the page total
 8  SELECT members...               <- the page itself
 9  SELECT member_intents...        <- used by the card
10  SELECT positions...             <- NOT read by to_member
11  SELECT educations...            <- NOT read by to_member
12  SELECT classes...               <- used by the card
13  SELECT ca_details...            <- NOT read by to_member
14  SELECT member_entries...        <- used by the card
15  ROLLBACK
```

Three of the eight query statements load relationships the directory card never reads, and they
are the two largest tables plus one. Combined with the three auth statements above, half of the
round trips on the product's hottest endpoint contribute nothing to the response. Median wall
time is 1.815s against a 0.351s no-DB baseline.

The first is safer: it makes an accidental profile-field read on a card path fail loudly.

### A job detail page fetches 100 companies to name one

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/app/(app)/jobs/[slug]/page.tsx:39-47`

**Evidence:**

```tsx
// The company map does not depend on the job, so it is not made to wait for it.
const [job, companies] = await Promise.all([
    loadJobByRef(slug).catch(...),
    loadCompanyMap().catch(() => null),
]);
```

The home page already avoids exactly this, and says so at `frontend/src/app/(app)/page.tsx:63-65`:

> The feed shows three jobs, so it reads at most three companies by id; it used to pull a hundred of them to name three.

**Why it matters:** The page renders one company. `job.company_id` is available the moment the job arrives, and `loadCompany(id)` exists at `api/server.ts:150-152`. The fix was applied on the home page and not carried here. And because `frontend/src/api/server.ts:56-63` forces `cache: "no-store"` whenever an access token is present, the `{ revalidate: 300 }` window on `loadCompanies` never applies to a signed-in member, so this is a fresh 100-row fetch on every job page view. The route is also `export const dynamic = "force-dynamic"` (line 22).

**Measured.** `dev-signedin.psv` shows the contrast between the two pages plainly. The home page,
which had the fix applied, resolves companies by id:

```
/  ... /api/v1/companies/53b80d17-... x1; /api/v1/companies/5687ac61-... x1; /api/v1/companies/8becbfa8-... x1;
```

while the job detail page fetches the whole list:

```
/jobs/plato-founding-engineer  ... /api/v1/companies/ x1; ...
```

and `GET /companies/?limit=100` is a 4,085-byte response costing 0.462s here, to print one name.

**Fix:** Drop `loadCompanyMap()` here. Fetch the job, then `job.company_id ? loadCompany(job.company_id) : null`. That is one extra sequential hop for one small row instead of a parallel 100-row page; if the waterfall matters, wrap the company panel in its own `<Suspense>` the way `PeopleAtCompany` already is at line 220.

### The home page fetches 50 announcements and 100 events to show two of each

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/api/server.ts:93-98`, consumed at `frontend/src/app/(app)/page.tsx:52-53,119,216`

**Evidence:**

```ts
export const loadAnnouncements = cache(() =>
    get<Page<Announcement> & { unread: number }>("/announcements/", { limit: 50 }),
);
export const loadEvents = cache((upcoming: boolean) =>
    get<Page<CommunityEvent>>("/events/", { upcoming, limit: 100 }),
);
```

```tsx
<AnnouncementList limit={2} initial={announcements ?? undefined} />
...
{events.items.slice(0, 2).map((event) => (
```

**Why it matters:** An announcement carries a body (`MAX_RICH_TEXT` is 20,000 characters per `backend/core/text.py:15`), so 50 of them is a payload measured in hundreds of kilobytes, fetched over the wire and serialised into the RSC stream, to render two headlines. Events are the same shape at twice the count. `docs/architecture.md` puts the home feed's whole purpose as "load fast enough to be worth opening".

**Fix:** Ask for what the page draws. `loadAnnouncements({ limit: 3 })` and `loadEvents(true, { limit: 3 })`, with the full-page views passing their own larger limit. Keep the `unread` count, which the announcements endpoint already returns independently of the page size.

### The app shell fetches 50 announcements on every page, for one number

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/app/(app)/layout.tsx:16-29`

**Evidence:**

```tsx
const [me, member, announcements] = accessToken
    ? await Promise.all([ loadMe().catch(...), loadMyMember().catch(...), loadAnnouncements().catch(...) ])
    : [null, null, null];
...
unread={announcements?.unread ?? 0}
```

**Why it matters:** The layout wraps every route under `(app)/`. Opening a job, a housing listing or a member profile pays for 50 announcement bodies so the header can draw a badge. `React.cache` does dedupe it with the home page's own call, so the home page pays it once rather than twice, but every other route pays it once for nothing.

**Measured.** `/api/v1/announcements/ x1` appears in the API call list of every one of the twelve
signed-in routes probed (`dev-signedin.psv`), including `/me`, `/network` and `/announcements`
itself, which between them make only three API calls each. `GET /announcements/?limit=50` is six
SQL statements and 1.124s on this host.

**Fix:** Give the announcements endpoint a cheap unread count (`GET /announcements/unread`, or `limit=0`), or call `loadAnnouncements({ limit: 1 })` here purely for the `unread` field.

### `React.cache` misses on every loader that takes a query object

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/api/server.ts:83-85,102-104,120,122-124,128,147-149`

**Evidence:** The file diagnoses the problem itself at lines 173-177:

> `React.cache` compares arguments by identity, and every caller builds a fresh array, so the cached function takes the ids as one sorted string. Two components asking for the same set then share a request.

and then applies that fix only to `lookupMembers` and `membersAtCompanies`. The other seven still take an object:

```ts
export const loadMembers = cache((query: Query) => get<Page<Member>>("/members/", query));
export const loadHousing = cache((query: Query) => get<Page<HousingListing>>("/housing/", query));
export const loadPathFlow = cache((query: Query) => get<PathFlow>("/paths/flow", query));
export const loadPathMembers = cache((query: Query) => get<Page<Member>>("/paths/members", query));
export const loadJobs = cache((query: Query) => get<Page<Job>>("/jobs/", query, { revalidate: 60 }));
export const loadCompanies = cache((query: Query) => get<Page<Company>>("/companies/", query, { revalidate: 300 }));
```

Every call site builds an object literal (`loadJobs({ status: "published", limit: 3 })` at `page.tsx:54`, `loadHousing({ status: "open", limit: 1 })` at `page.tsx:55`, `loadPathFlow({})` at `paths/page.tsx:19`), so no two calls ever share a cache entry.

**Why it matters:** The file's opening comment states the rule these wrappers exist to enforce ("a page and its children asking for the same thing costs one request per render rather than one per component"), and for six of the nine loaders the wrapper is inert. It is not currently causing a duplicate request that I could trace, which is why this is not Critical, but it is a guarantee the code claims and does not provide: the next component that asks for `loadJobs({status:"published",limit:3})` alongside the home page will silently double the request.

**Fix:** Apply the same trick the file already uses. Make the cached function take a canonical string key and expose a thin wrapper:

```ts
const jobsPage = cache((key: string) => get<Page<Job>>("/jobs/", JSON.parse(key), { revalidate: 60 }));
export const loadJobs = (query: Query) => jobsPage(stableStringify(query));
```

with one shared `stableStringify` that sorts keys.

### The job board runs a router navigation on every keystroke

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/features/jobboard/JobsBrowser.tsx:65,209-216` via `frontend/src/lib/urlState.ts:23-39`

**Evidence:**

```tsx
const setQuery = (value: string) => setParams({ q: value });
...
<input type="search" ... value={query} onChange={(event) => setQuery(event.target.value)} />
```

and

```ts
router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
```

**Why it matters:** Typing "engineer" issues eight `router.replace` calls. Each is an App Router transition on a route marked `export const dynamic = "force-dynamic"` (`jobs/page.tsx:16`), so each re-runs `useSearchParams`, re-derives `selection`, `pool`, `counts` and `shown` (four `useMemo`s, `JobsBrowser.tsx:54-123`) and re-renders the whole board including every `JobRow`. The input is controlled by the URL value, so the character does not appear until that round completes. The repository already has both fixes: `frontend/src/lib/useDebounced.ts` and the `useDeferredValue` pattern documented at `components/MemberGrid.tsx:49-57`.

**Fix:** Hold the input in local state, and push to the URL through `useDebounced(draft, 250)` in an effect, or defer the derived list with `useDeferredValue`. The other controls (checkboxes, sort) are discrete and are fine writing to the URL immediately.

### Supabase Storage opens a new HTTP client, and a new TLS connection, per call

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/backend/media/infrastructure/supabase_storage.py:36,48,61,79`

**Evidence:** All four methods do `async with httpx.AsyncClient(timeout=_TIMEOUT) as client:` and close it on exit.

**Why it matters:** `read_media` calls `signed_url` on every image request (`backend/media/api/router.py:129`), and `signed_url` is a POST to Supabase. A page showing 20 housing photos or job logos therefore costs 20 fresh TLS handshakes to the Supabase host from the API process, with no connection reuse and no keep-alive, on the critical path of rendering images. `docs/architecture.md` section 9 describes this as the normal read path, so it is the hot path, not an edge case.

**Fix:** Hold one `httpx.AsyncClient` for the adapter's lifetime. The adapter is already a singleton behind `get_blob_storage` (`backend/media/infrastructure/__init__.py:17-32`), so create the client in `__init__` and close it in the app's `_lifespan` (`backend/core/app.py:208-211`), next to the existing `get_async_engine().dispose()`.

### Consider: the Sankey layout rescans all links twice per link

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/features/community/paths/layout.ts:142-150,216-229`

**Evidence:**

```ts
for (const link of [...links].sort((a, b) => b.count - a.count)) {
    ...
    const sourceTotal = totalFor(links, link.source_stage, link.source_group, "source") || 1;
    const targetTotal = totalFor(links, link.target_stage, link.target_group, "target") || 1;
```

where `totalFor` filters the whole `links` array and reduces it.

**Why it matters:** O(L squared). With four stages and a dozen groups each the link count stays in the low hundreds, so this is a handful of milliseconds today and the memo at `PathsChart.tsx:48` keeps it off the interaction path. It is only a problem if the group vocabulary grows.

**Fix:** Precompute two `Map<string, number>` totals in one pass before the loop, keyed by `stage::group`.

### Consider: the dead grid runs its filter twice per keystroke

**Location:** `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/src/components/MemberGrid.tsx:86,92-96`

**Evidence:**

```ts
const filtered = useMemo(() => filterWith(applied), [filterWith, applied]);
...
useEffect(() => {
    for (const m of filterWith(query).slice(0, PRELOAD_COUNT)) {
```

**Why it matters:** `filterWith` scans all ~1,400 members. Line 86 runs it on the deferred value and line 93 runs it again on the live value, so every keystroke does two full passes plus 48 image preloads. Listed for completeness only: nothing imports this component (see the dead-code finding), so the right fix is deletion.

### FYI: performance items checked that are fine

- **No N+1 in the repositories.** Every relationship is `selectin`, and `one_member_per_company` (`members_repository.py:126-162`) genuinely resolves 50 company names in one statement using a `VALUES` table plus a LATERAL join.
- **Pagination is enforced.** `backend/core/api/pagination.py:17` caps `limit` at 100 with `le=100`, and every list route takes `PageParamsDep`.
- **The Ask rate limit is real and shared.** `backend/core/llm/quota.py:28-41` is a single UPSERT with the window pinned by `date_trunc('minute', now())`, so there is no read-modify-write race, and it holds across processes. `TokenBucketLimiter._buckets` (`rate_limit.py:29`) is an unbounded module-level dict, but the key is `str(actor.member_id)` or the literal `"unbound"` (`ask_service.py:219`), so it is bounded by the member count and is not a leak.
- **No unrevoked object URLs or un-cleared timers in live code.** `ImageUpload` uses no `createObjectURL`; `useDebounced` clears its timer (`lib/useDebounced.ts:15`). The one uncleared timer is `lib/profiles.ts:59`, inside the dead island.
- **Ask does not fire per keystroke.** `AskLine.tsx:43-47` is a form submit, not an `onChange`, so the quota that `tests/integration/test_ask.py` guards is not being burned by typing.
- **`matching_ids`** (`members_repository.py:77-91`) is deliberately unbounded and returns every matching id so the Paths flow covers the whole cohort. The docstring argues the case and the directory is a few thousand rows. Fine at this scale; worth a ceiling if the directory ever grows an order of magnitude.

---

## Tests

The backend's test story is genuinely strong: 488 unit tests pass, and the performance-relevant
behaviours the brief named are each covered by a named test (see the FYI under Correctness).
Two gaps:

**The frontend has no test runner and no tests at all.** `find frontend -name '*.test.*' -o -name
'*.spec.*' -o -name 'vitest.config*' -o -name 'jest.config*'` returns nothing outside
`node_modules`, and `frontend/package.json` has no `test` script:

```json
{ "dev": "next dev", "build": "next build", "start": "next start", "lint": "eslint",
  "typecheck": "tsc --noEmit", "ingest": "node scripts/ingest.mjs",
  "generate:api": "...", "check:api": "node scripts/check-api.mjs" }
```

Two of this review's four blocking findings are in pure, trivially testable functions:
`safeNext` (5 lines, one input, one output) and `ImageUpload`'s upload loop. `lib/format.ts`
(`safeUrl`, `slugify`, `formatSalary`, `paragraphs`), `api/people.ts` (`avatarOf`,
`toNetworkMember`) and `features/community/paths/layout.ts` (`layoutFlow`) are all pure and all
untested. Adding Vitest and a dozen tests for these would have caught both bugs.

**No unit test asserts the pagination cap.** `tests/unit/test_core_gaps.py` covers
`page_params()` defaults and a valid page but never `limit=101`, so the `le=100` in
`backend/core/api/pagination.py:17` is only guarded by FastAPI itself.

## Change sizing

Per the skill's sizing table, ~1000 changed lines is "too large, split it". The three commits that
landed during this session total 3,010 files and 79,593 insertions, and the session began with the
entire application uncommitted. The skill does carve out an exception for "complete file deletions
and automated refactoring where the reviewer only needs to verify intent", which covers the
`communitytool/` and `jobboard/` removals and the bulk of the insertions (1,250 avatar `.webp`
files, ~1,200 `public/profiles/*.json` fixtures, and the generated `schema.d.ts` and
`openapi.json`). The hand-written code is still far past reviewable-in-one-sitting, and this
review is necessarily a prioritised pass over the paths the brief named rather than a line-by-line
read of everything. Flagging for the record, not as a blocker: the work is done and splitting it
retroactively would cost more than it saves. The lesson is forward-looking, and the commits made
during this session are the right size.

---

## Review Checklist

```markdown
## Review: New CDTM Community platform (backend + Next.js 16 frontend), working tree

### Context
- [x] I understand what this change does and why
      (AGENTS.md, docs/architecture.md, CONTEXT-MAP.md, ADRs 0001-0007, TODO.md all read)

### Correctness
- [~] Change matches spec/task requirements
      Backend matches the documented contracts. Frontend has one type error against the
      generated schema (LoginForm.tsx:94) and one data-loss bug (ImageUpload.tsx:55-78).
- [~] Edge cases handled
      Backend: yes, thoroughly. Frontend: the >100-companies and >100-jobs cases are
      unhandled and silent.
- [x] Error paths handled
      One error envelope, one ApiError adapter, run_db maps every driver error, and every
      server loader has a deliberate .catch() policy.
- [~] Tests cover the change adequately
      Backend yes (488 passing, the named behaviours all covered). Frontend has no tests
      and no test runner.

### Readability
- [x] Names are clear and consistent
      The domain vocabulary from CONTEXT-MAP is used carefully, on both sides.
- [x] Logic is straightforward
- [ ] No unnecessary complexity
      ~800 lines of orphaned code from the previous app (MemberGrid and its cluster);
      rate_limit_key triplicated; eleven frontend files over 250 lines.

### Architecture
- [~] Follows existing patterns
      Backend layering is clean and verified. Frontend features/community/ recreates the
      context name ADR 0007 removed and CONTEXT-MAP forbids.
- [~] No unnecessary coupling or dependencies
      features/jobboard reaches into features/community/ask for shared machinery that the
      backend keeps in core.
- [x] Appropriate abstraction level
      The BlobStorage port, the read ports and the Actor seam are all earning their keep.

### Security
- [x] No secrets in code
- [~] Input validated at boundaries
      Media, request bodies and most query parameters are well constrained. /members/at-company
      names and /paths/flow groups have no length limit.
- [x] No injection vulnerabilities
      All SQL parameterised; the one dynamic fragment picks its column from a fixed dict.
- [x] Auth checks in place
      Authorization lives in application/ services, never in a router, as documented.
- [~] External data sources treated as untrusted
      safeUrl is correct; safeNext is bypassable with a backslash (open redirect).

### Performance
- [x] No N+1 patterns
      Verified by counting statements per request, not by reading: every endpoint issues a fixed
      number of queries regardless of row count. `at-company` really does resolve 50 companies in
      one LATERAL query. The waste is a fixed over-fetch, not an N+1.
- [ ] No unbounded operations
      Measured: 12 statements for one directory page, of which 6 do no work for the response
      (3 auth prelude, 3 unused eager loads); a committed write to accounts on every request; loadCompanyMap capped at 100 with no fallback; 50 announcements and
      100 events fetched to render two of each; a new TLS connection per Storage call.
- [x] Pagination on list endpoints
      Every list takes skip/limit, capped at 100.

### Verification
- [x] Tests pass (backend: 488 passed, 1 skipped, exit 0)
- [ ] Build succeeds (frontend typecheck exit 2, lint exit 1)
- [x] Manual verification done
      The API was run against the configured Postgres with SQL echo on, and every list endpoint
      was probed for statement count and wall time; the twelve signed-in frontend routes were
      probed for API call counts. No repository file was modified. Raw data in the scratchpad
      (`counts.psv`, `timings.psv`, `dev-signedin.psv`, `echo-slices/`).

### Verdict
- [ ] **Approve**: ready to merge
- [x] **Request changes**: issues must be addressed
```

## Verdict: Request changes

The design here is better than most of what I review: the bounded contexts are real, the layering
rules are enforced in the code and not only in the docs, the error envelope and the storage port
are genuinely well built, and the comments explain the concrete reason rather than restating the
line below them. The backend would be an approve on its own. The frontend is where the problems
are, and four of them block.

**Blocking:**

1. **`npm run typecheck` fails** (`frontend/src/app/login/LoginForm.tsx:94`). The frontend does
   not build. Fix the property read or extend `DevMemberOption` and regenerate the client.
2. **`npm run lint` fails** (2 errors in `frontend/src/components/MemberGrid.tsx:98,138`). Both
   are in the orphaned component cluster, so deleting that cluster closes them; confirm with the
   author before removing.
3. **Open redirect in `frontend/src/lib/safeNext.ts:11`.** `/login?next=/\evil.example` bounces a
   member to another origin immediately after sign-in. Verified against the WHATWG URL parser.
   Replace the prefix check with parse-and-compare, and add the test.
4. **Multi-image upload loses everything but the last file**
   (`frontend/src/components/ImageUpload.tsx:55-78`). Stale closure over `urls`; the comment on
   line 71 describes a functional update the code does not perform.

**Strongly recommended before this goes in front of members** (not blocking merge, but each is a
real cost on a real page): the per-request `accounts` write
(`backend/identity/infrastructure/account_repository.py:58-88`), the six eagerly loaded
relationships on directory search (`backend/members/infrastructure/orm_models.py:88-111`), and
`loadCompanyMap()` on the job detail page (`frontend/src/app/(app)/jobs/[slug]/page.tsx:46`),
which the home page already shows the fix for.

**Worth filing rather than fixing now:** the `features/community/` naming, the missing frontend
test runner, and the `at-company` / `paths/flow` length limits.
