# FastAPI backend request-path performance audit

Repo: `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job`. Read-only. Skills applied:
performance axis of `code-review-and-quality` (its `references/performance-checklist.md` does
not exist in the installed skill), and `fastapi-best-practices`.

## How this was measured

- Server: `DATABASE_URL=postgresql+asyncpg://localhost:5432/cdtm_perf_audit LLM_PROVIDER=none
  uv run uvicorn backend.core.main:app --port 8765`, local scratch DB
  (1,115 members, 10,108 positions, 6,000 jobs, 300 companies, 2,000 housing listings,
  600 events, 1,200 announcements). `GET /health` answered `{"status":"ok","database":"ok"}`.
  `LLM_PROVIDER` was forced to `none` so no provider spend; the root `.env` has
  `LLM_PROVIDER=openai`. The real Supabase pooler was never contacted.
- Token: `AUTH_DEV_LOGIN_ENABLED=true` in `.env`, so
  `POST /api/v1/auth/dev/login {"member_slug":"charlotte-kobiella"}` minted an HS256 token
  (`backend/identity/api/dev_router.py:26`). The first slug tried (`julia-balowski`) 409'd at
  `accounts.upsert`: the scratch DB already had an `accounts` row on that e-mail with a
  different `auth_user_id`, so the insert hit the unique e-mail index. A member with no
  account row was used instead.
- Timings: `curl -s -o /dev/null -w '%{time_total}'`, one warm-up then 5 runs, median reported.
  Loopback, warm PG cache, no network. Treat these as a floor: against the Supabase pooler
  every round trip in the "DB round trips" column costs real RTT.
- Bytes: `%{size_download}` without and with `-H 'Accept-Encoding: gzip'`.
- Round trips: the server was restarted with `DATABASE_ECHO=true` and every statement was
  attributed to the request that followed it in the log. "DB round trips" = the authenticated
  Principal prelude counted as 4 (SELECT accounts, UPDATE accounts, COMMIT, SELECT refresh)
  plus the statements the endpoint itself issued. `BEGIN`/`ROLLBACK` bookkeeping excluded.

## Measurement table

| Endpoint | Auth | Median ms | Bytes raw | Bytes gzip | DB round trips |
| --- | --- | --- | --- | --- | --- |
| `GET /members/?limit=60` | bearer | 57.9 | 59,977 | 59,977 | 13 (4 prelude + 9) |
| `GET /members/?limit=60` | anon | 5.4 | 110 (401) | 110 | 0 |
| `GET /members/?q=product&limit=20` | bearer | 51.8 | 21,697 | 21,697 | 13 (4 + 9) |
| `GET /members/facets` | bearer | 15.3 | 11,447 | 11,447 | 7 (4 + 3) |
| `GET /members/tarak-a-552078312` | bearer | 28.8 | 3,995 | 3,995 | 12 (4 + 8) |
| `GET /members/lookup?ids=…` (10 ids) | bearer | 39.7 | 11,416 | 11,416 | 12 (4 + 8) |
| `GET /members/at-company?company=…` (5 real names) | bearer | 87.8 | 5,611 | 5,611 | 13 (4 + 9) |
| `GET /paths/flow` | bearer | 40.0 | 27,452 | 27,452 | 11 (4 + 7) |
| `GET /paths/groups` | bearer | 19.6 | 574 | 574 | 7 (4 + 3) |
| `GET /jobs/` (limit 20) | bearer | 15.2 | 19,184 | 19,184 | 6 (4 + 2) |
| `GET /jobs/` (limit 20) | anon | 12.1 | 19,184 | 19,184 | 2 |
| `GET /companies/?limit=100` | bearer | 8.2 | 49,005 | 49,005 | 2 (no prelude: route has no auth dep) |
| `GET /companies/?limit=100` | anon | 13.9 | 49,005 | 49,005 | 2 |
| `GET /housing/` (limit 20) | bearer | 20.7 | 10,115 | 10,115 | 6 (4 + 2) |
| `GET /events/?upcoming=true&limit=100` | bearer | 53.7 | 43,735 | 43,735 | 6 (4 + 2) |
| `GET /announcements/?limit=50` | bearer | 20.6 | 17,327 | 17,327 | 7 (4 + 3) |
| `GET /auth/me` | bearer | 13.6 | 495 | 495 | 5 (4 + 1) |
| `GET /members/me` | bearer | 128.8 | 7,441 | 7,441 | 12 (4 + 8) |
| `GET /network/saved` | bearer | 74.6 | 2 (`[]`) | 2 | 5 (4 + 1; +1 more when non-empty) |

Anonymous rows are omitted where the route is 401-only (`/members/*`, `/paths/*`, `/housing/`,
`/events/`, `/announcements/`, `/auth/me`, `/members/me`, `/network/saved` all returned 401
without a bearer, in 3-17 ms). `/jobs/` and `/companies/` serve anonymous callers.

**Compression is off.** `bytes_raw == bytes_gzip` on every single endpoint, including the
60 KB members page and the 49 KB companies page. There is no `Content-Encoding` on any
response. Proven by measurement, and by grep: no `GZipMiddleware`, no brotli, in
`backend/core/app.py`.

## Findings

| Severity | Category | Location | Evidence | Impact | Recommended fix |
| --- | --- | --- | --- | --- | --- |
| Critical | middleware | `backend/core/app.py:214-305` (`create_app`; middleware wired at :241, :275, :280) | Measured: `size_download` identical with and without `Accept-Encoding: gzip` on all 19 endpoints. `grep -rn 'GZipMiddleware\|brotli\|orjson'` over `backend/` returns nothing. | JSON compresses 5-10x. `/members/?limit=60` ships 60 KB, `/companies/?limit=100` 49 KB, `/events/?limit=100` 44 KB, every single request, over the public internet. | `app.add_middleware(GZipMiddleware, minimum_size=1000)` (stdlib, already available via starlette). Add it *inside* `create_app` before CORS. |
| Critical | n+1 / caching | `backend/identity/infrastructure/account_repository.py:71-95`, called from `backend/identity/application/auth_service.py:70` on every request through `PrincipalDep` (`backend/identity/api/deps.py:88-99`) | Echo log shows on every authenticated request: `SELECT accounts …` / `UPDATE accounts SET last_sign_in_at=…` / `COMMIT` / `SELECT accounts …` (the `refresh`). 4 round trips and a row write before the handler starts. | 4 of 13 round trips on `/members/?limit=60` and 4 of 5 on `/auth/me` are the prelude. Every GET is a write, so every GET takes a row lock on `accounts` and generates WAL. Against a pooler this is ~4 RTT of pure overhead per request. | Split the read from the write: `SELECT` the account, and only `UPDATE last_sign_in_at` when the stored value is older than N minutes (`row.last_sign_in_at < now() - interval '5 min'`). Drop `refresh(row)` entirely: the object is already populated. Optionally short-TTL cache the verified-claims -> Account mapping in process (keyed by `sub`, 60 s) so most requests do zero statements. |
| High | n+1 | `backend/members/infrastructure/orm_models.py:88-111` (six `lazy="selectin"` relationships) vs `backend/members/infrastructure/_mappers.py:32-55` (`to_member`) | Echo log for `GET /members/?limit=60`: count, page, then `member_intents`, `positions`, `educations`, `classes`, `ca_details`, `member_entries`, then `select member_id from accounts`. `to_member` reads only `row.classes`, `row.entry`, `row.intents`: `positions`, `educations`, `ca_detail` are fetched and discarded. `positions` is 10,108 rows in the scratch DB. | 3 wasted round trips per list request, and the `positions` load for a 60-row page pulls hundreds of position rows (title, company, description, dates) that are thrown away. Largest single contributor to the 57.9 ms on `/members/?limit=60`. | Make the eager loads opt-in per query: change the relationships to `lazy="raise"` (or `lazy="select"`) and add explicit `.options(selectinload(...))` in `get_by_slug`/`get_by_id` only; list paths (`search`, `get_many`, `one_member_per_company`) load `classes`, `entry`, `intents` only. Add `.options(load_only(...))` to drop `search_text`, `summary` and `company_info` (JSONB) from list queries. |
| High | caching | Every list/reference route: `backend/members/api/members.py:112-119` (`/facets`), `backend/paths/api/paths.py:50` (`/groups`), `backend/paths/api/paths.py:36` (`/flow` unfiltered), `backend/jobboard/api/companies.py:18` (`/companies/`) | `grep -rn -iE 'cache-control\|etag\|cachetools\|TTLCache'` over `backend/` hits only `backend/media/api/router.py:45,138`. No API JSON response carries `Cache-Control`, `ETag` or `Last-Modified`. Verified: response headers on `/members/facets` carry only the five security headers plus `content-type`/`content-length`. | `/members/facets` (11 KB, 3 statements), `/paths/groups` (3 statements), `/paths/flow` unfiltered (7 statements, 27 KB) and `/companies/` (49 KB) are derived from data that only changes on the offline loader run. Every page view in the SPA re-computes them. | See the caching plan below. |
| High | serialization / pagination | `backend/announcements/api/announcements.py:21-31`; `unread_count` already exists at `backend/announcements/application/announcement_service.py:77` and `backend/announcements/infrastructure/announcements_repository.py:156` | `Announcement.body` is `str = Field(min_length=1)` with no max in the domain (`backend/announcements/domain/announcements.py:14`); the platform ceiling is `MAX_RICH_TEXT = 20_000` (`backend/core/text.py`). `AnnouncementPublic` is the bare domain model, so `GET /announcements/?limit=50` returns 50 full bodies. **No route exposes `unread_count`**: grep of `backend/announcements/api/` shows only `/`, `/{id}`, `/{id}/read`. | The layout fetches 50 announcements on every page just to render an unread badge. At 20 KB bodies that is a 1 MB response for a number. Measured 17 KB here only because the synthetic bodies are short. | Add `GET /announcements/unread-count` returning `{"unread": n}` (1 statement, ~40 bytes) and have the layout call that. Add an `AnnouncementSummaryPublic` for the list that omits `body` (or truncates it to a 300-char excerpt), keeping the full body on `GET /announcements/{id}`. |
| High | serialization | `backend/jobboard/api/schemas.py:30-37` + `backend/jobboard/domain/job.py:68`; `backend/housing/api/schemas.py:13-23` + `backend/housing/domain/housing.py:33,43`; `backend/events/api/schemas.py:10-16` + `backend/events/domain/events.py:27` | `JobPublic`/`HousingListingPublic`/`EventPublic` are bare subclasses of the domain aggregate, so the list endpoints return `Job.description` (unbounded in the domain, capped at `MAX_RICH_TEXT` on write), `HousingListing.description` + `photo_urls`, `Event.description`, plus `must_have_skills`/`nice_to_have_skills`/`languages` arrays. | `/jobs/` at limit 20 measured 19 KB with short synthetic descriptions; with real 20 k-char descriptions the same page is 400 KB. `/events/?limit=100` already measures 44 KB. | Introduce `JobSummaryPublic` / `HousingListingSummaryPublic` / `EventSummaryPublic` for the list routes (title, slug, company, location, salary band, dates, counts) and keep the full aggregate on the by-id/by-slug routes. This is the `UserPublic` vs list-DTO split the `fastapi-best-practices` DTO section calls for. |
| High | ask | `backend/members/application/ask_service.py:175-187` (`_viewer_context`) | It calls `self._members.get_by_id(actor.member_id)`, which is `SqlMemberRepository.get_by_id` (`backend/members/infrastructure/members_repository.py:104-112`): the **full profile** load: 1 row select + 6 `selectin` loads + the `_claimed_ids` query = 8 statements, plus `current_group_of` = 1. All to read `class_label`, `max(classes.year)` and `location`. | Every `POST /members/ask/` and every `POST /members/ask/explain` (which the UI may fire per keystroke) pays 9 extra round trips before the model call. | Add a narrow repository method that selects `class_label`, `location` and the class years for one member in one statement, and use it here. |
| Medium | ask | `backend/members/api/ask.py:39,47`; `backend/paths/api/paths.py:47`; `backend/members/api/ask.py:56` | `AskAnswerPublic.model_validate(answer.model_dump())`: serialise the whole answer (up to 100 `Member` models) to dicts, then re-validate every field. Same pattern for the flow (`PathFlowPublic.model_validate(flow.model_dump())`) and the interpretation. `backend/members/infrastructure/_mappers.py:58-59` does it again per profile (`to_member(row).model_dump()` then `MemberProfile(...)`). | Double pydantic work on the hottest object in the answer. `PathFlowPublic` on an unfiltered flow is 27 KB of nodes and links being dumped and re-parsed. | `XPublic` subclasses `X`, so `AskAnswerPublic.model_validate(answer)` (or `model_construct` from the parent's `__dict__`) works without the dict round trip. For `to_profile`, build the `MemberProfile` fields directly instead of dumping the `Member`. |
| Medium | serialization | `backend/core/app.py:224-233` (`FastAPI(...)` constructor) | No `default_response_class=ORJSONResponse`; `orjson` is not in `pyproject.toml` dependencies. Every response is encoded by starlette's `JSONResponse`, i.e. `json.dumps` on a `jsonable_encoder` output, after pydantic has already validated the `response_model`. | On a 60 KB members page the encode is measurable CPU on a single-threaded event loop. FastAPI's `response_model` validation also re-validates objects the routers already validated by hand (`MemberPublic.model_validate(m)` at `backend/members/api/members.py:66` and the same in every board router): the model is validated twice per item. | Add `orjson` and `default_response_class=ORJSONResponse`. Separately, since every router already constructs the exact `XPublic` type it declares, `response_model` re-validation is pure duplicate work: either drop the hand-validation in the routers or set `response_model_exclude_unset=False` + rely on the return annotation only. |
| Medium | ask | `backend/members/application/ask_service.py:79-107`, `backend/core/llm/_http.py:25-73`, `backend/core/llm/quota.py:50-65` | The completion is a single blocking `POST` (`response_format: json_schema`), not streamed; `LLM_TIMEOUT_S` default 20 s with `_RETRIES = 1`, so worst case is ~40 s inside a request the member is waiting on. No caching of any kind by normalised question: grep finds no cache in `backend/core/llm/`. The quota is 1 UPSERT + 1 COMMIT (2 round trips) per question, before validation of anything else. A new `httpx.AsyncClient` is built per call (`_http.py:40`), documented as deliberate. | A repeated question re-pays the full model latency (docs/ask.md measures 1.5-5 s) and the token cost. `/explain` shares the meter but not a cache, so a UI that previews per keystroke pays per keystroke. | Add an in-process `TTLCache` keyed on `(board, normalised question, language, viewer class/year/location/group)` holding the `AskInterpretation` for ~10 minutes: the translation is the expensive, deterministic part, and the search re-runs against live data. Hang one `httpx.AsyncClient` off the app lifespan (`backend/core/app.py:208-212` already has a `_lifespan`) instead of per call. |
| Medium | pagination | `backend/network/api/network.py:27-32` (`/network/saved`), `:53-62` (`/network/intros`) | Both are declared `response_model=list[...]` with no `PageParamsDep`, no `skip`, no `limit`. `NetworkService.list_saved` (`backend/network/application/network_service.py:37-40`) fetches every saved row and then every card for them. | Unbounded response. A member who saved 500 people gets 500 full `NetworkMemberPublic` cards in one body, and the repository has no ceiling. Violates the `{items,total}` + `le=100` convention `AGENTS.md` states for every list. | Give both routes `PageParamsDep` and the `{items,total}` envelope like every other board. |
| Medium | pagination | `backend/members/infrastructure/members_repository.py:78-92` (`matching_ids`), used at `backend/members/api/ask.py:45-46` | `matching_ids` runs `select(MemberRow.id)` with **no limit** and returns every matching id; those go into `PathFilters(member_ids=tuple(ids))` and then into all 7 statements of `paths_repository.flow` (`backend/paths/infrastructure/paths_repository.py:65-103`). | A broad Ask ("everyone") binds ~1,100 UUIDs into 7 separate queries. The docstring acknowledges "a few thousand rows"; it grows with the roster and there is no ceiling. | Cap it (e.g. 5,000) and, better, pass the *filter* down as a subquery rather than a materialised id list, or have Paths join `member_paths` against the same filtered member subquery. |
| Medium | pagination | `backend/paths/application/path_service.py:52-58` (`members_in`) | `member_ids_in(...)` returns all ids for the group, then `self._cards.page(ids, skip=skip, limit=limit)` pages **in Python**. The `le=100` on `PageParamsDep` bounds the response, not the work. | The whole group's id list is materialised on every page request of `/paths/members`. | Push `skip`/`limit` into the SQL that selects the ids. |
| Low | n+1 | `backend/members/api/members.py:112-119` (`/facets`); `backend/paths/infrastructure/paths_repository.py:204-214` (`groups`); `backend/announcements/api/announcements.py:25-26` | `/facets` awaits `list_classes()`, `list_majors()`, `count()` in sequence (3 round trips). `groups()` loops the three stage columns awaiting a `DISTINCT` each (3 round trips). The announcements route awaits `service.list(...)` then `service.unread_count(...)` (2 round trips). | 3 serial RTTs where 1 would do. On loopback this is the 15.3 ms of `/facets`; against the pooler it is 3 x RTT. | Merge each set into one statement (`UNION ALL` of three aggregates for `/facets`; one `SELECT DISTINCT stage, group FROM (unnest…)` or three `array_agg` subselects for `groups`; a window `count(*) FILTER (WHERE not read)` alongside the announcements page). Note `asyncio.gather` is **not** the fix here: a single `AsyncSession` is not concurrency-safe, so gathering would need separate sessions and therefore separate pooled connections. |
| Low | n+1 | `backend/members/application/member_service.py:151-163` (`_unique_slug`) | Loops `await self._members.find_id_by_slug(f"{base}-{n}")` one round trip at a time until a free slug is found. | Write path only (`POST /members/me`), and collisions are rare. | One query: `select slug from members where slug like base || '%'` and pick the first gap. |
| Low | blocking | `backend/media/infrastructure/supabase_storage.py:36,48,61,79`; `backend/media/api/router.py:120-132` | Every storage call builds `async with httpx.AsyncClient(...)`: a fresh connection pool and TLS handshake per call. `read_media` signs a fresh URL per request (`SIGNED_URL_SECONDS = 600`) and returns a 307 with **no** `Cache-Control`, so the browser re-asks the API for every `<img>` on every page load; only the local-disk fallback path sets `IMMUTABLE_CACHE`. | One extra HTTPS round trip to Supabase per image per page view. | Reuse one `AsyncClient` from the app lifespan. Cache the signed URL in process for ~half its lifetime keyed on `(bucket,key)`, and put `Cache-Control: private, max-age=300` on the redirect so the browser reuses it. |
| Nit | middleware | `backend/core/app.py:240-273` (`_body_size_limit`), `:274-278` (`_security_headers`) | Two `@app.middleware("http")` decorators, which is `BaseHTTPMiddleware`. It wraps each request in an anyio task group and streams the response through a memory object stream. | Neither buffers the whole body (both only touch headers), so the cost is per-request task-group overhead rather than memory. Real but small. | Rewrite both as one pure-ASGI middleware class; `_body_size_limit` only reads `content-length` and `_security_headers` only mutates the response start message, so neither needs `BaseHTTPMiddleware`. |
| Nit | middleware | `backend/core/app.py:280-287` (CORS), `backend/core/main.py` | CORS is correctly restricted to `APP_CORS_ORIGINS` with two request headers. No request-logging middleware exists (only per-error `logger.warning`/`logger.exception`), so there is no per-request latency signal in production. `main.py` is a bare `app = create_app()` with no worker/loop configuration; `uvicorn[standard]` is a dependency so uvloop 0.22.1 and httptools 0.8.0 are installed and `loop="auto"`/`http="auto"` picks them. No `--proxy-headers`/`--forwarded-allow-ips` is set anywhere, and no process manager config (no Dockerfile, Procfile or platform toml in the repo). | No p50/p95 visibility; behind a proxy the client IP and scheme will be wrong. Single worker unless the deploy overrides it. | Add a small ASGI timing/logging middleware. Document the production launch line: `--workers N --proxy-headers --forwarded-allow-ips=… --timeout-keep-alive 30`. |

### Concrete caching plan

Nothing in the request path is safe to cache in a *shared* proxy while it is behind a bearer
token, but the following are principal-independent in content:

| Endpoint | Depends on principal? | Recommendation |
| --- | --- | --- |
| `GET /members/facets` | No (`_: PrincipalDep` is a gate only, `members.py:112`) | `Cache-Control: private, max-age=300` + in-process `TTLCache(maxsize=1, ttl=300)`. Changes only on the loader run. |
| `GET /paths/groups` | No (`paths.py:50`) | Same: `private, max-age=600` + `TTLCache(maxsize=1, ttl=600)`. Three `DISTINCT` scans for a value that changes when the classifier reruns. |
| `GET /paths/flow` (no query params) | No (`paths.py:36`) | `private, max-age=300` + `TTLCache(maxsize=64, ttl=300)` keyed on the `PathFilters` tuple. 7 statements and 27 KB per call today. |
| `GET /companies/` | No: the route has **no** auth dependency at all (`companies.py:18-26`); echo log confirms zero prelude statements | Genuinely public: `Cache-Control: public, max-age=300` + ETag. 300 rows that change on the loader run. |
| `GET /members/{slug}`, `/members/`, `/members/lookup`, `/members/at-company` | Yes: `_redact` (`member_service.py:165-186`) varies the body by viewer | Not cacheable as-is. If wanted, cache the *un-redacted* row objects in process and redact per request. |
| `GET /announcements/`, `/events/`, `/housing/`, `/network/*`, `/auth/me`, `/members/me` | Yes (`is_read`, `my_rsvp`, `view_count`, owner state) | `Cache-Control: no-store`. Fix the payload sizes instead. |

`cachetools` is not currently a dependency; `functools.lru_cache` will not do here because the
values must expire on the loader run, so add `cachetools` (small, no transitive deps) or write
a 20-line TTL dict. Whichever is chosen, the loader (`scripts/platform/load_community.py`)
should be able to bust it, otherwise a reload is invisible for the TTL.

### Pagination limits: verified

`page_params` (`backend/core/api/pagination.py:17`) enforces `ge=1, le=100` and is used by
`/members/`, `/paths/members`, `/jobs/`, `/companies/`, `/seekers/`, `/housing/`, `/events/`,
`/announcements/` and `/auth/accounts`. The exceptions:

- `GET /members/lookup`: `Query(max_length=50)` on the `ids` list (`members.py:70-75`) plus a
  second `[:50]` truncation in the service (`member_service.py:193`). Capped, correct.
- `GET /members/at-company`: same `max_length=50` (`members.py:88-94`) and `[:50]`
  (`member_service.py:203`). Capped, correct. Note it costs 9 statements regardless of how
  many names are asked for, because the batch query is followed by the six-way `selectin`
  load of the resulting member rows.
- `GET /network/saved` and `GET /network/intros`: **no limit at all** (see the table above).
- `GET /auth/dev/members`: `MEMBER_PICKER_LIMIT = 20` hard-coded (`dev_router.py:25`),
  development only.

## What is already done well

- **No true N+1 anywhere in an application service.** Every place the shape invited one has
  been batched deliberately: `MemberService.contacts_at` (`member_service.py:196-211`) does one
  batched `one_member_per_company` and one `get_many`; `NetworkService._cards`
  (`network_service.py:106-110`) resolves all ids in one call for both saved cards and both
  sides of every intro request; events RSVP counts are correlated scalar subqueries in the
  page query (`events_repository.py:20-43`), not a query per event; announcement read state is
  the same. `GET /events/?limit=100` costs 2 statements for 100 events. The listed suspects
  (jobs+companies, events+RSVP, housing+owner, announcements+read state, intro requests,
  saved cards) are all clean.
- **No blocking I/O on the event loop.** `grep` for `time.sleep`, `requests.`, `urllib`,
  `Image.open`, `hashlib`, `subprocess`, bare `open(` over `backend/` and `infrastructure/`
  finds exactly one hit, `urllib.parse.quote` (a pure function). There is no Pillow and no
  `sharp`-equivalent: `backend/media/infrastructure/images.py` identifies images by magic
  bytes only (`sniff_image_content_type`, lines 26-39), which is both faster and safer than
  decoding. `LocalDiskStorage` explicitly routes every read/write/unlink through
  `anyio.to_thread.run_sync` (`local_disk.py:42-68`) with a comment saying why. Both LLM
  adapters are async `httpx` with a real timeout and exactly one retry, and they parse a
  strict JSON schema rather than repairing prose.
- **The Ask design keeps the model off the data path.** The LLM only ever emits a validated
  `MemberQuery`, and `RulesQueryTranslator` answers when the provider is down, so a provider
  outage degrades quality instead of returning 503. The quota is one statement with the count
  read back in the same round trip (`quota.py:28-41`), with an in-process bucket as the
  fallback.
- **Query construction is sound.** `search_text` has a GIN trigram index
  (`orm_models.py:120-123`), user `%`/`_` are escaped before `ILIKE` (`backend/core/sql.py`),
  every statement is parameterised, and `statement_timeout` is set per connection
  (`infrastructure/db.py:79-83`) so no single query can pin a worker.
- **Connection handling is right.** One `AsyncSession` per request, `pool_pre_ping`,
  `pool_recycle=1800` (`db.py:94-95`), and asyncpg's statement cache disabled specifically when the URL is a
  PgBouncer pooler (`db.py:71,85-88`): the failure mode most people find in production.
- **Body size is capped before a handler reads it** (`app.py:240-273`, `MAX_JSON_BODY_BYTES`),
  and `MAX_RICH_TEXT`/`MAX_NOTE` give every free-text field a ceiling, which is what keeps the
  serialization findings above at "large" rather than "unbounded".
- `uvicorn[standard]` is a hard dependency, so uvloop and httptools are in place rather than
  the pure-Python fallbacks.

## Things I could not verify

- `GET /network/saved` measured against an empty saved list (2-byte body), so its per-item
  cost is inferred from the code, not measured.
- No Ask endpoint was timed: `LLM_PROVIDER` was forced to `none` to avoid spending against the
  key in `.env`. The Ask findings are from reading the code and the echo log shape, not from a
  live provider call.
- Timings are loopback with a warm cache against a scratch DB; they establish relative cost
  and round-trip counts, not production latency.
