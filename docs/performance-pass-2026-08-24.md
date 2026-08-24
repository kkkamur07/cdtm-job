# Performance pass, 24 August 2026

Seven parallel audits of the Next.js frontend, the FastAPI backend, Supabase auth and storage, and the Postgres schema, followed by seven implementation rounds. Every recommendation was re-validated against the code before it was changed; what was not worth doing is listed with the reason. The per-item evidence (file:line, measurements, verification output) is in [`performance-pass-2026-08-24/`](performance-pass-2026-08-24/): the audits `fe-waterfalls`, `fe-bundle`, `fe-client`, `supabase-auth`, `postgres`, `backend`, `runtime`, `review`, and the implementation reports `impl-fe1` to `impl-fe3` and `impl-be1` to `impl-be4`.

Skills applied: Vercel react-best-practices, supabase, supabase-postgres-best-practices, code-review-and-quality.

## How it was measured

All measurement ran on loopback against local scratch copies of the data (real roster of 1,115 members and 10,108 positions; synthetic boards of 6,000 jobs, 2,000 listings, 1,200 announcements with 9,600 reads). The remote database was never used by the app, Alembic, tests or scripts during the pass. Statement counts come from `DATABASE_ECHO=true` attributed per request; plans from `EXPLAIN (ANALYZE, BUFFERS)`; bytes from `curl` with and without `Accept-Encoding: gzip`. The frontend was measured with a production build and a dev build, signed in and signed out, counting backend calls per server render. No browser-side metrics were captured, so LCP, INP and input-latency claims are reasoned from the code.

The floor no code change removes: against the configured database, `/health` (one `SELECT 1`) takes 294 to 414 ms, while the same query over an open `psql` session is 39 to 49 ms. The API and the database sit in different regions. Every round trip saved below is worth a full RTT there; moving the API next to the database remains the single largest available win.

## API after the pass

Statements exclude BEGIN/COMMIT. "Before" is the audit's count with the 4-statement token prelude; "after" was re-measured on the same code paths. Latency is loopback median of five, gzip enabled.

| Endpoint | Statements before | After | Raw bytes | Gzip | Median | Cache-Control |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `GET /members/?limit=60` | 12 | 6 | 59,976 | 19,483 | 24 ms | |
| `GET /members/?q=maria` | 12 | 6 | 13,449 | 5,229 | 24 ms | |
| `GET /members/facets` | 6 | 1 | 11,447 | 2,331 | 6 ms | private, max-age=300 |
| `GET /members/{slug}` | 11 | 9 | 16,369 | 6,692 | 13 ms | |
| `GET /members/lookup` (50 ids) | 11 | 6 | 47,129 | 15,101 | 23 ms | |
| `GET /members/at-company` (2 names) | 12 | 7 | 2,434 | 1,251 | 18 ms | |
| `GET /paths/flow` | 10 | 1 (warm cache; 2 cold) | 27,452 | 1,778 | 5 ms | private, max-age=300 |
| `GET /paths/groups` | 6 | 1 | 574 | 574 | 6 ms | private, max-age=600 |
| `GET /paths/members` | 6 | 3 | 38,548 | 15,979 | 12 ms | |
| `GET /jobs/` | 5 | 2 | 16,973 | 1,930 | 12 ms | |
| `GET /companies/?limit=100` | 2 | 0 | 49,005 | 3,670 | 4 ms | public, max-age=300 |
| `GET /housing/` | 5 | 2 | 9,184 | 1,623 | 8 ms | |
| `GET /events/?upcoming=true&limit=100` | 5 | 2 | 41,628 | 3,981 | 11 ms | |
| `GET /announcements/?limit=50` | 6 | 3 | 17,326 | 2,205 | 15 ms | |
| `GET /announcements/unread-count` (new) | n/a | 2 | 15 | 15 | 8 ms | |
| `GET /auth/me` | 4 | 2 | 476 | 476 | 8 ms | |
| `GET /members/me` | 11 | 9 | 7,063 | 3,220 | 17 ms | |
| `GET /network/saved` | 4 | 2 | 22 | 22 | 5 ms | |

The steady-state prelude is now one `SELECT accounts`. The 1.5 to 2 s first byte the audit saw on every signed-in page was three shell calls (auth/me, 50 announcements, members/me) against the remote database; the shell now calls the 15-byte count endpoint, and pages start their own fetches in parallel with the member gate.

## Postgres plans, before and after migration 002

Same rows, same database, with and without the twelve new indexes. Shared buffer hits are the metric.

| Query | Before (buffers / ms) | After | Plan change |
| --- | ---: | ---: | --- |
| jobs default page | 230 / 87.5 | 3 / 0.07 | Seq Scan + top-N sort to Index Scan on `ix_jobs_published_created` |
| who works at X, 8 names | 22,337 / 616 | 1,596 / 155 | per-name full scan to BitmapOr over two trigram indexes |
| announcements page with is_read | 148 / 32.7 | 65 / 16.2 | expression index on the real sort, FK index on reads |
| housing page | 56 / 2.8 | 4 / 0.44 | Seq Scan + sort to Index Scan on created_at |
| `saved_members WHERE saved_member_id` | 47 / 83.7 | 3 / 0.58 | Seq Scan to Index Only Scan |
| `event_rsvps WHERE member_id` | 73 / 78.6 | 3 / 1.0 | Seq Scan to Index Only Scan |
| `positions.company ILIKE` in EXISTS | 459 / 45.5 | 102 / 37.6 | Bitmap Index Scan on `ix_positions_company_trgm` |
| paths flow, six aggregates | ~150 over 6 trips | 31 / 2.9, 1 trip | one GROUPING SETS statement |
| directory `?q=` count + page | 3,929 / 2 trips | 1,949 / 1 trip | window `count(*) OVER ()` |

Kept out of the migration: GIN on `members.skills` and trigram on `members.location` were created and the planner still chose a seq scan at 1,115 rows. The window count costs more on the jobs first page (245 buffers over one trip vs 3 + 16 over two) because the index lets the plain page stop early; it was kept for the saved round trip and is written down in `database-design.md` 8.4.

## What was done

Frontend, data flow: `force-dynamic` removed from the three job-board routes (it implied `fetchCache = force-no-store`); `gatedData()` starts page fetches in parallel with the member gate; the shell reads `GET /announcements/unread-count`; `/paths` and `/me` seed React Query from the server payload; the home page fetches two announcements under a size-keyed query key; poster lookups stream in their own Suspense boundary; the job page loads one company by id; one session read then `getClaims(token)`; seven dead files deleted.

Frontend, bundle and client: logo 1,168,266 bytes to 590; search and filter state local-first with the URL updated in a transition; multi-file upload fixed (it kept only the last file); `preconnect` to the API and Supabase origins; memoized rows with stable callbacks; Sankey layout O(L log L) instead of O(L^2) (one accumulation pass plus the existing sort); hoisted `Intl` formatters and RegExps; proxy matcher and prefetch skip; `content-visibility` on rows, not containers; `priority` on the first housing cards; async image decoding; token split out of the session context; housing writes invalidate only the boards and the touched listing; save/unsave writes the server row into the cache; INITIAL_SESSION as the restore path; hoisted skeleton rows; one PathsChart chunk; dead `remotePatterns` removed; Typewriter pauses in hidden tabs; `safeNext` open redirect closed.

Backend: gzip; the per-request `accounts` write replaced by a write only on change or after `AUTH_SIGN_IN_TOUCH_SECONDS`; JWKS with a real TTL, 5 s timeout, verification off the event loop, pre-warm and issuer check; one Storage HTTP client, immutable upload cache headers, signed URL cache with `Cache-Control`; pure-ASGI request guards with route-template timing; pooler detection by port, `SET LOCAL statement_timeout` under transaction pooling, a boot log naming both resolved databases and the pool budget; three unused member relationships `lazy="raise"` with explicit profile loads; window counts everywhere; flow, facets and groups as one statement each; `backend/core/cache.py` TTL cache on principal-independent reads with `Cache-Control`; narrow Ask viewer context; Ask interpretation cache and a lifespan-owned LLM client; list summary DTOs without descriptions and skill arrays; paginated `/network/saved` and `/network/intros`; ids paged in SQL; one-query slug allocation; input caps; migration `002_hot_path_indexes`; RLS guard test; docs corrected with measured numbers.

## Validated and deliberately not done

- `ORJSONResponse`: FastAPI 0.141 deprecates it and already serialises to JSON bytes via Pydantic when a response model is set; enabling it put routes back on `jsonable_encoder`.
- A `sub -> Principal` TTL cache: `claim_member`, `bind_account_to_member` and `set_admin` mutate a live principal; the person who just claimed their member would see it fail for the cache window.
- Keyset pagination for the directory: no UI path pages deeper than the first page.
- Moving `getIdentity()` out of the root layout: every loader reads cookies, so no route can be static, and `/login` and `/onboarding` consume the root identity.
- Firing authed queries before the token is restored: the bearer exists only after `setAccessToken`, so the query would 401 and is not retried.
- An empty-string validator for `DATABASE_MIGRATOR_URL`: `env_ignore_empty` already handles it; a test pins that.
- Tier-2 indexes (positions company/title trigram, educations, array GINs): thresholds recorded in `database-design.md`.

## Open decisions

- `tests/integration/test_auth.py::test_unverified_top_level_email_is_rejected` fails on committed code independent of this pass: `jwt_verifier.py` treats `app_metadata.provider == "google"` as a verified address, the test's token factory sets that provider and expects rejection. One of the two must change.
- If the Supabase project is on the legacy HS256 secret, every page pays two `/auth/v1/user` network calls that no frontend change removes; asymmetric signing keys make both verifications local.
- Public buckets for `job-images` and `housing-photos` would let the CDN serve them directly; the signed-URL cache is the private-bucket best case.
- `/me` shows the 100 most recent saved people and intro requests with a "most recent of N" line; a pager is the remaining piece. Membership no longer depends on that page (see the review section).

## Code review before merge

Four reviewers (correctness, readability and architecture, security, performance and tests) read the full branch diff independently, following the code-review-and-quality skill's five axes. Verdicts: one Critical, thirteen required items, no Critical or required item on the security axis. Everything Critical and required was fixed on the branch before merge; the cheap Consider items were taken as well.

- Critical (correctness): the Save button derived "already saved" from a shortlist page capped at 100, so a member past the cap read as unsaved, and the resulting `PUT` carried `note: null` and wiped the note. Now `PUT /network/saved/{id}` leaves an existing note alone when the body omits `note` (an explicit `null` still clears it), `GET /network/saved/ids` returns the whole id set for the button, `GET /network/intros?with_member_id=` answers "did I already ask" without scanning the capped history, and the toggle invalidates on settle so the cache is right even when the optimistic path has nothing to update.
- Facets cache was never cleared by profile writes: a new member's major was missing from the filter bar for up to ten minutes. Cleared on create and update.
- List summaries cut the wire but not the query: jobs, housing and events lists still selected `description`. The three repositories now select exactly the summary columns, pinned by compiled-statement tests, and the domain summaries, DTOs and SELECT lists are asserted equal.
- The proxy skipped the session refresh on prefetch on a false premise (prefetch responses do set cookies) and left the one path that cannot write a rotated token to do the refresh. The skip is gone.
- `verify_async` moved every asymmetric verification onto the shared anyio thread pool. It now verifies inline on a warm JWKS, refreshes cold sets under a single-flight lock on a dedicated limiter, and negative-caches unknown key ids for 30 s.
- Two TTL cache implementations: the media signed-URL cache is on `backend/core/cache.py` now, so `clear_all()` and the test fixture reach it, and `cachetools` is gone from the dependencies.
- Security Consider items taken: `today` is in the Ask viewer context so the interpretation key covers it; `member_ids` is in the flow cache key; `/companies/` sends `Vary: Origin` next to its public `Cache-Control`; `industry`, `hq_city` and `skill` are capped like the other filters.
- Tests: `TTLCache`, `page_with_total` and the five `Cache-Control` headers are unit tested; the facets, flow and interpretation cache invalidations have tests; the note-preserving `PUT` and the ids endpoint have integration tests.
- Readability: dead query keys removed, one `ANNOUNCEMENTS_PAGE` constant, `MemberGate` doc block back on `MemberGate`, `verify` dropped from the `TokenVerifier` port, `preconnect` with `crossOrigin`, hoisted `useSyncExternalStore` subscriptions in the typewriter, gzip level 6, and the inaccurate claims in this document corrected (the flow is one statement warm and two cold; the Sankey layout is O(L log L)).

Left as recorded, by decision rather than oversight: the pre-existing auth test failure, asymmetric signing keys, public buckets, the pager for the `/me` lists, and the private-bucket upload `Cache-Control` (a year, immutable) that outlives a signed URL after a delete.

## Caveats

- Migration 002 uses `CREATE INDEX CONCURRENTLY`, so it can run against the live database without blocking writes; run it through a direct connection rather than the pooler.
- Back/forward navigation no longer restores the jobs search text or housing chips; the URL mirrors the settled value.
- The `SET LOCAL statement_timeout` path is tested for what it issues, not against a live port-6543 endpoint.
- Gates at the end of the pass, after the review below: `poe lint` and `poe format-check` clean; `poe test-fast` 686 passed; integration 280 passed and the one pre-existing auth failure above; `npm run typecheck`, `npm run lint`, `npm run build` clean; OpenAPI regenerated.
