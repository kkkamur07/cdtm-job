# CDTM Community, end-to-end runtime measurements

Measured 2026-08-24 on macOS (darwin 25.5.0). All raw logs, scripts and CSVs are in this
scratchpad directory.

## What was actually run, and the deviations

| Thing | Value |
| --- | --- |
| Database | `select count(*) from members` = **1115**. Also: accounts 2, jobs 8, housing_listings 6, events 4, announcements 3, companies 7. |
| Database location | **Not local.** Root `.env` `DATABASE_URL` points at `aws-1-eu-north-1.pooler.supabase.com:5432` (Supabase session pooler). This dominates every number below. |
| Backend | A pre-existing uvicorn was already on :8000 (PID 79149, not mine). I started **my own uvicorn on :8010** with `--access-log`, `APP_CORS_ORIGINS=http://localhost:3000,http://localhost:3100`, log at `backend8010.log`. Reason: I need the access log to count per-render API calls, and the running instance only allows CORS for :3000 so a frontend on :3100 could not have made browser-side calls. Same code, same `.env`, same database. Health path is `/health` (not `/api/v1/health`); `{"status":"ok","database":"ok"}`. |
| Frontend build | `npm run build` in `frontend/` **FAILS**: `src/app/login/LoginForm.tsx(94,49) error TS2339: Property 'email' does not exist on type '{ class_label?…; id; name; slug }'`. Turbopack compiled fine; only `tsc` failed. Because I may not modify tracked files, I copied the frontend to `scratchpad/fe-prod`, added `typescript: { ignoreBuildErrors: true }` to that copy's `next.config.ts`, and built there. The build then succeeded (24.1s compile). Source is otherwise byte-identical to the repo. |
| Production server | `next start --port 3100` from `fe-prod`, built with `NEXT_PUBLIC_API_URL=http://localhost:8010`. All 23 routes are dynamic (`ƒ`); only `/icon.svg` is static. |
| Dev server | `next dev --port 3101` from `scratchpad/fe-dev`, same source, `.env.local` patched to `NEXT_PUBLIC_AUTH_MODE=dev`. |
| `frontend/.env.local` | Present. `NEXT_PUBLIC_API_URL=http://localhost:8000`, `NEXT_PUBLIC_AUTH_MODE=supabase`, `NEXT_PUBLIC_SUPABASE_URL=<redacted>`, `NEXT_PUBLIC_SUPABASE_ANON_KEY=<redacted>`. |
| Signed-in session | `POST /api/v1/auth/dev/login {"member_slug":"raul-berganza"}` on :8010, then `POST /api/auth/dev-session` with the token, cookie `cdtm_dev_session` saved with `curl -c`. Verified: dev-mode `/me` contains "Berganza", signed-out `/me` contains "Sign in". |

### The one measurement that could not be taken: signed-in in production mode

`frontend/src/auth/mode.ts` starts with `if (process.env.NODE_ENV === "production") return "supabase";`.
Next inlines `NODE_ENV` at build time, so a production build **ignores the dev-session cookie
entirely**. Verified empirically: against the production server on :3100, `/me` with the cookie
and `/me` without it are byte-identical (4220 bytes gzip both, `cmp` says IDENTICAL, both render
"Sign in with CDTM Google").

There is no Supabase session available to mint instead, so **the signed-in column is measured in
dev mode on :3101 and is labelled `DEV MODE` throughout.** Every dev-mode number carries Next's
dev-server overhead, which the signed-out rows put at roughly +35 to +70 ms of TTFB.

### Browser step: not done

Chrome tools failed twice with "Browser extension is not connected". Step 7 (post-hydration XHR
counts, console warnings, `performance.getEntriesByType`, DOM node counts) was **skipped**. In its
place I measured the static asset weight the HTML references (below); post-hydration fetches,
console warnings and DOM size are **unmeasured**.

---

## Route table, PRODUCTION build, signed-out (:3100)

Median of 5 runs, warm server, `-H 'Accept: text/html' --compressed`. `size` is gzip wire bytes;
`raw` is the uncompressed HTML. `API calls` is the cold count (one request against a
just-restarted server), taken from the uvicorn access log.

| Route | Status | TTFB (ms) | Total (ms) | size gzip (B) | raw HTML (B) | API calls |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | 200 | 73.7 | 81.9 | 4192 | 15346 | 0 |
| `/members/benedikt-alb` | 200 | 34.2 | 62.2 | 5212 | 17711 | 1 |
| `/network` | 200 | 19.0 | 21.2 | 4290 | 16150 | 0 |
| `/paths` | 200 | 26.4 | 35.3 | 4303 | 17080 | 0 |
| `/jobs` | 200 | 19.5 | 34.5 | 8647 | 36151 | 3 |
| `/jobs/plato-founding-engineer` | 200 | 17.6 | 30.9 | 7904 | 28678 | 3 |
| `/companies` | 200 | 20.0 | 21.4 | 5774 | 26026 | 0 |
| `/housing` | 200 | 12.5 | 13.6 | 4288 | 16976 | 0 |
| `/housing/9465d6a3-…4d` | 200 | 34.8 | 53.4 | 5309 | 19869 | 1 |
| `/events` | 200 | 12.1 | 14.5 | 4249 | 15877 | 0 |
| `/announcements` | 200 | 16.5 | 20.7 | 4249 | 15919 | 0 |
| `/me` | 200 | 36.7 | 44.8 | 4220 | 15853 | 0 |
| `/post` | 200 | 20.8 | 25.5 | 4210 | 16427 | 0 |
| `/login` | 200 | 16.7 | 31.2 | 3131 | 10367 | 0 |

Cold (first request after a server restart, single sample, signed-out, production):

| Route | TTFB | Total |
| --- | --- | --- |
| `/jobs` | **224.3 ms** | 350.7 ms |
| `/jobs/plato-founding-engineer` | 36.9 ms | 73.1 ms |
| `/companies` | 30.2 ms | 33.5 ms |
| `/members/benedikt-alb` | 24.3 ms | 31.2 ms |
| `/housing/9465d6a3-…4d` | 30.1 ms | 34.2 ms |

`/jobs` and `/jobs/[slug]` are the only loaders with `next: { revalidate: 60 }`
(`src/api/server.ts`), so a warm server serves them from the data cache and the warm TTFB of
19.5 ms hides the 224 ms cold cost.

## Route table, DEV MODE, signed-in as `raul-berganza` (:3101)

Median of 5, after a full warm-up pass so no route pays first-compile cost. **Dev mode.**

| Route | Status | TTFB (ms) | Total (ms) | size gzip (B) | raw HTML (B) | API calls |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | 200 | **1932.1** | **4645.2** | 15583 | 57670 | **13** |
| `/members/benedikt-alb` | 200 | 1860.9 | 2115.6 | 12845 | 43596 | 5 |
| `/network` | 200 | 1767.4 | 1770.8 | 6588 | 27071 | 3 |
| `/paths` | 200 | 1777.4 | 2734.4 | 15339 | **109373** | 6 |
| `/jobs` | 200 | 1820.8 | 3251.6 | 11677 | 51275 | 7 |
| `/jobs/plato-founding-engineer` | 200 | 1854.5 | 4680.8 | 15296 | 52250 | 7 |
| `/companies` | 200 | 1794.6 | 1796.6 | 7569 | 34659 | 5 |
| `/housing` | 200 | 1721.7 | 3672.1 | 11028 | 46869 | 5 |
| `/housing/9465d6a3-…4d` | 200 | 1823.8 | **4828.6** | 16858 | 63753 | 7 |
| `/events` | 200 | 1712.9 | 2092.3 | 8576 | 32765 | 4 |
| `/announcements` | 200 | 1785.1 | 1790.6 | 7309 | 30508 | 3 |
| `/me` | 200 | 1831.5 | 1833.1 | 6246 | 26643 | 3 |
| `/post` | 200 | 1851.4 | 1859.7 | 6743 | 27419 | 3 |
| `/login` | 200 | 122.2 | 147.1 | 4497 | 16470 | 0 |

Next's own dev log attributes essentially all of it to app code, not to the framework, e.g.
`GET /me 200 in 1831ms (next.js: 5ms, proxy.ts: 5ms, application-code: 1821ms)` and
`GET /housing/… 200 in 4.9s (next.js: 69ms, proxy.ts: 31ms, application-code: 4.8s)`.
So the ~1.8 s floor is backend round trips, not the dev server. A production signed-in render
would plausibly land near 1.7 s, but that is an **inference, not a measurement**.

## Route table, DEV MODE, signed-out (:3101)

For calibrating how much of the signed-in column is dev overhead. Compare with the production
signed-out table above: the same routes are 12-74 ms in production and 47-107 ms in dev.

| Route | TTFB (ms) | Total (ms) | size gzip (B) | API calls |
| --- | --- | --- | --- | --- |
| `/` | 57.7 | 65.6 | 5592 | 0 |
| `/members/benedikt-alb` | 83.3 | 86.8 | 6372 | 1 |
| `/network` | 54.1 | 56.2 | 5779 | 0 |
| `/paths` | 51.8 | 53.7 | 5883 | 0 |
| `/jobs` | 80.4 | 83.4 | 9804 | 2 |
| `/jobs/plato-founding-engineer` | 106.8 | 115.3 | 9389 | 2 |
| `/companies` | 58.6 | 60.1 | 7225 | 0 |
| `/housing` | 68.6 | 70.3 | 5833 | 0 |
| `/housing/9465d6a3-…4d` | 98.7 | 100.7 | 6714 | 1 |
| `/events` | 56.4 | 59.1 | 6372 | 0 |
| `/announcements` | 50.3 | 51.7 | 5674 | 0 |
| `/me` | 49.3 | 50.4 | 5688 | 0 |
| `/post` | 54.7 | 56.2 | 5722 | 0 |
| `/login` | 46.9 | 50.1 | 4485 | 0 |

---

## Backend API calls per server render

From the uvicorn access log on :8010, one request per route, log delta attributed to that render.

### Signed-in (13, 7, 7, 7, 6, 5, 5, 5, 4, 3, 3, 3, 3, 0)

Every signed-in page pays a **three-call shell tax** before it renders anything of its own:
`GET /api/v1/auth/me`, `GET /api/v1/announcements/?limit=50`, `GET /api/v1/members/me`.

| Route | n | Endpoints |
| --- | --- | --- |
| `/` | **13** | shell(3) + `/events/?upcoming=true&limit=100`, `/members/me/intents`, `/network/saved`, `/housing/?status=open&limit=1`, `/jobs/?status=published&limit=3`, `/companies/{id}` **×3 (one per job, N+1)**, `/members/lookup?ids=…×3`, `/members/?intent=cofounding&limit=5` |
| `/members/benedikt-alb` | 5 | shell(3) + `/paths/members/benedikt-alb`, `/members/benedikt-alb` |
| `/network` | 3 | shell(3) only. The saved list is fetched client-side. |
| `/paths` | 6 | shell(3) + `/paths/groups`, `/members/facets`, `/paths/flow` |
| `/jobs` | 7 | shell(3) + `/companies/?limit=100`, `/jobs/?status=published&limit=100`, `/members/lookup?ids=…×8`, `/members/at-company?company=…×7` |
| `/jobs/plato-founding-engineer` | 7 | shell(3) + `/companies/?limit=100`, `/jobs/slug/plato-founding-engineer`, `/members/lookup?ids=…×1`, `/members/?company=Plato&limit=6` |
| `/companies` | 5 | shell(3) + `/companies/?limit=100`, `/jobs/?status=published&limit=100` |
| `/housing` | 5 | shell(3) + `/housing/?status=open&limit=100`, `/members/lookup?ids=…×6` |
| `/housing/{id}` | 7 | shell(3) + `/housing/{id}`, `/members/lookup?ids=…×1`, `/housing/?city=Munich&status=open&limit=5`, `/members/?location=Munich&limit=6` |
| `/events` | 4 | shell(3) + `/events/?upcoming=true&limit=100` |
| `/announcements` | 3 | shell(3) |
| `/me` | 3 | shell(3) |
| `/post` | 3 | shell(3) |
| `/login` | 0 | none |

### Signed-out (production, cold)

| Route | n | Endpoints |
| --- | --- | --- |
| `/members/benedikt-alb` | 1 | `/members/benedikt-alb` → **401** |
| `/jobs` | 3 | `/jobs/?status=published&limit=100` → 200; `/members/lookup?ids=…×8` → **401**; `/members/at-company?company=…×7` → **401** |
| `/jobs/plato-founding-engineer` | 3 | `/jobs/slug/…` → 200; `/members/lookup` → **401**; `/members/?company=Plato&limit=6` → **401** |
| `/housing/{id}` | 1 | `/housing/{id}` → **401** |
| all other 10 routes | 0 | none |

Signed-out renders still fire 5 authenticated calls across 4 routes that can only ever return 401,
and each one costs a full backend round trip.

## Individual backend endpoint latency (:8010, direct curl, 3 runs, median)

Same process, same database as the page renders.

| Endpoint | Median |
| --- | --- |
| `/health` (a `SELECT 1` + DB probe) | **0.37 s** (12-run range 0.294-0.414) |
| `/api/v1/companies/` | 0.46 s |
| `/api/v1/auth/me` | 0.91 s |
| `/api/v1/network/saved` | 0.91 s |
| `/api/v1/members/me/intents` | 0.94 s |
| `/api/v1/events/?upcoming=true&limit=100` | 1.03 s |
| `/api/v1/jobs/?status=published&limit=100` | 1.03 s |
| `/api/v1/housing/?limit=50` | 1.04 s |
| `/api/v1/announcements/?limit=50` | 1.10 s |
| `/api/v1/paths/groups` | 1.15 s |
| `/api/v1/members/facets` | 1.20 s |
| `/api/v1/members/me` | **1.59 s** |
| `/api/v1/paths/flow` | **1.72 s** |
| `/api/v1/members/?limit=24` | **1.95 s** |

For comparison, the same database queried directly with `psql` inside one open session:
`select 1` = 39-49 ms, `select count(*) from members` = 84 ms, `select count(*) from jobs` = 58 ms.
A fresh `psql` process (connect + TLS + query + exit) is 0.41-0.58 s.

## Client-side, per route

**Not measured in a browser** (extension unavailable). What follows is the static weight the served
HTML references, fetched over HTTP and summed.

| Route | Mode | JS files | JS gzip | CSS gzip | `<img>`/next-image tags |
| --- | --- | --- | --- | --- | --- |
| `/` | prod, out | 12 | 202,203 B | 11,542 B | 0 |
| `/members/benedikt-alb` | prod, out | 12 | 203,370 B | 11,542 B | 0 |
| `/paths` | prod, out | 13 | 207,051 B | 11,542 B | 0 |
| `/jobs` | prod, out | 12 | 203,352 B | 11,542 B | 0 |
| `/housing` | prod, out | 12 | 208,478 B | 11,542 B | 0 |
| `/` | DEV, in | 19 | 868,869 B | 12,568 B | 4 |
| `/members/benedikt-alb` | DEV, in | 19 | 870,783 B | 12,568 B | 2 |
| `/paths` | DEV, in | 21 | 879,627 B | 12,568 B | 1 |
| `/jobs` | DEV, in | 19 | 871,390 B | 12,568 B | 7 |
| `/housing` | DEV, in | 20 | 898,498 B | 12,568 B | 10 |

Dev-mode JS is unminified and not comparable to production; the production row (~200-208 KB gzip
of JS per route, essentially the same 12-13 chunks everywhere) is the real figure.

**Unmeasured, because the browser step was skipped:** post-hydration XHR/fetch counts to the API,
image request counts and bytes, `domContentLoadedEventEnd` / `loadEventEnd`, resource totals by
`initiatorType`, DOM node counts, and console/hydration warnings. Code inspection shows
client-side `useQuery` hooks in `src/api/hooks/{auth,community,directory,jobboard,me,members}.ts`
and `src/features/community/ask/useAsk.ts`, so there is real post-hydration traffic (`/network`
renders with only the 3 shell calls server-side and must fetch its saved list in the browser), but
none of it was observed.

---

## Top 5 slowest things observed, with evidence

1. **Every backend call carries a ~330 ms floor that is not query time.** `/health`, which does one
   `SELECT 1`, is 0.294-0.414 s over 12 consecutive runs. The identical query over `psql` in an
   already-open session to the same database is 39-49 ms. `DATABASE_URL` in the root `.env` is
   `…@aws-1-eu-north-1.pooler.supabase.com:5432/postgres`, a remote Supabase pooler, not a local
   Postgres, and `infrastructure/db.py` sets `pool_pre_ping=True` (an extra round trip per checkout)
   plus `statement_cache_size=0` because the host matches `pooler.supabase.com`. Nothing else in the
   stack is within an order of magnitude of this.

2. **`/` signed-in issues 13 backend requests in one render and takes 1932 ms to first byte,
   4645 ms to last.** Access log for one render: `/auth/me`, `/announcements/?limit=50`,
   `/members/me`, `/members/me/intents`, `/network/saved`, `/events/`, `/housing/?limit=1`,
   `/jobs/?limit=3`, then **three separate `/api/v1/companies/{id}` calls, one per job card** (a
   textbook N+1 across the network), `/members/lookup`, `/members/?intent=cofounding&limit=5`.

3. **A three-call shell tax on every signed-in page.** `/auth/me` + `/announcements/?limit=50` +
   `/members/me` fire on all 13 signed-in routes including `/post`, `/network` and `/me`, which need
   nothing else. Measured cost of those three alone: 0.91 + 1.10 + 1.59 = 3.60 s serial, ~1.6 s
   parallel, which is exactly the ~1.72-1.93 s TTFB floor seen on every single signed-in row,
   `/network` (3 calls, 1767 ms) and `/announcements` (3 calls, 1785 ms) included.

4. **The three heaviest endpoints are all on member/path reads:** `/api/v1/members/?limit=24` at
   1.95 s, `/api/v1/paths/flow` at 1.72 s, `/api/v1/members/me` at 1.59 s. `/paths` calls
   `paths/flow` + `members/facets` (1.20 s) + `paths/groups` (1.15 s) on top of the shell, and emits
   the largest document in the app at 109,373 bytes of raw HTML (15,339 gzip).

5. **Signed-out renders spend round trips on calls that can only 401.** Cold production access log:
   `/members/[slug]` → 1 call, 401. `/jobs` → 3 calls, 2 of them 401
   (`/members/lookup?ids=…×8`, `/members/at-company?company=…×7`). `/jobs/[slug]` → 3 calls, 2 of
   them 401. `/housing/[id]` → 1 call, 401. That is 5 wasted backend round trips for a visitor who
   is shown a sign-in gate anyway. Visible in the timings: `/members/benedikt-alb` 34.2 ms and
   `/housing/{id}` 34.8 ms versus 12-20 ms for the gated routes that call nothing.

Honourable mention, not a latency item: **`/jobs` warm TTFB of 19.5 ms is a cache artefact.** It is
224 ms cold. `loadJobs` and `loadJobBySlug` are the only loaders with `next: { revalidate: 60 }`.

## Other findings worth reporting

- **`npm run build` does not pass in the repo as committed.** `src/app/login/LoginForm.tsx:94`
  reads `picked?.email`, but `DevMemberOption` (from the generated `schema.d.ts`) has no `email`
  field, and `backend/identity/api/dev_router.py` documents that deliberately: "The reply carries
  the slug and not the e-mail." So the type error is a real behaviour bug too, not only a build
  break: the member picker cannot prefill the address.
- **Dev login is dead in any production build.** `src/auth/mode.ts` returns `"supabase"` whenever
  `NODE_ENV === "production"`, and `NODE_ENV` is inlined at build time, so the `cdtm_dev_session`
  cookie is never read. Confirmed by byte-identical signed-in and signed-out `/me` responses.
- **Backend CORS defaults to `http://localhost:3000` only** (`APP_CORS_ORIGINS` in `.env`), so a
  frontend served from any other port cannot make browser-side API calls without changing it.
- The uvicorn access log emits **two lines per 401** (an `api_error ref=… status=401` line plus the
  access line); naive line counting doubles the call count. The numbers above count only access
  lines.
