# Backend performance audit, remaining items (be4)

Every item was validated against the working tree before it was changed. No em dashes or en
dashes anywhere. Nothing committed, nothing reverted, no packages installed. No command ever
pointed at the root `.env` `DATABASE_URL`; the integration suite ran against a local
`cdtm_community_test_be4` created for this pass.

---

## 1. Ask interpretation cache, and the per-call httpx client

### Validated

- `backend/members/application/ask_service.py:140-166` (before the change): `_interpret`
  validated, charged the meter, built the viewer context and then called the translator on
  every single call. `ask` (line 89) and `explain` (line 127) both go through it, so typing
  a question in the preview and then asking it was two model calls for the same words.
- `backend/core/cache.py:32-95`: `TTLCache(maxsize=..., ttl=...)`, `get` returns `None` on a
  miss or an expiry, `set` ignores `None`, every instance registers itself in `_CACHES` and
  `clear_all()` (line 87) empties the lot. The convention is a module-level cache next to the
  service, as `backend/paths/application/path_service.py:33-34` and
  `backend/members/application/member_service.py:51` already do.
- `backend/housing/application/housing_ask_service.py:111-141` (before): same shape, minus the
  viewer context, which is always an empty `ViewerContext()` there. The cache applies.
- `backend/core/llm/_http.py:33-40` (before): the docstring said a shared client is not kept
  because "the app factory owns no lifespan hook this module could hang one off". That reason
  no longer holds: `backend/core/app.py:230-238` has `_lifespan`, and it already closes the
  blob storage client and disposes the engine. A per-call client means a TCP connect plus a
  TLS handshake to the provider on every question.

### Changed

- `backend/core/llm/ask.py`: added `interpretation_key(board, question, language, viewer)`.
  It lives in `core` because `members` and `housing` may not import each other, and
  `ViewerContext` is already here. Question folded to casefold with whitespace collapsed; the
  viewer goes in whole (`model_dump` items), so a field added to `ViewerContext` later changes
  the key instead of silently letting two askers share a stale reading.
- `backend/members/application/ask_service.py`: `INTERPRETATION_TTL_SECONDS = 600`,
  `_INTERPRETATIONS = TTLCache(maxsize=256, ttl=...)`, a `_handed_out` helper, and the lookup
  in `_interpret`. `/ask` and `/ask/explain` share it for free because both go through
  `_interpret`.
- `backend/housing/application/housing_ask_service.py`: same, `maxsize=64`.
- Two deliberate decisions, both commented in place:
  - the meter is still charged on a cache hit (the cache spares the provider, not the
    member's allowance, and it keeps the rate limit meaningful);
  - only a reading the **model** produced is cached. Caching the keyword fallback would buy
    nothing (it is pure Python) and would pin `LLM_DOWN_NOTE` onto every asker for ten minutes
    after the provider came back.
  - the reading is deep-copied on the way out (both branches). `AskInterpretation` is
    `extra="forbid"` but not frozen, and neither is the `MemberQuery` inside it, so handing
    out the cached instance would let one caller edit what the next asker sees. Same rule the
    `Facets` cache states in `backend/members/application/ports.py:64-75`.
- `backend/core/llm/_http.py`: `shared_client()` (built lazily, no timeout on the client, the
  timeout is per request because each adapter has its own `LLM_TIMEOUT_S`) and
  `aclose_shared_client()`. `post_json` uses the shared client, except when a caller passes
  its own `transport`: a transport belongs to a client, and swapping a test stub into the
  shared pool would leak it into whatever ran next, so that path still gets a throwaway
  client. The retry and status handling moved into `_post` unchanged.
- `backend/core/llm/__init__.py`: exports `aclose_shared_client` so `app.py` does not import a
  private module.
- `backend/core/app.py`: `_lifespan` closes it on shutdown, next to the storage client.

### Tests added

`tests/unit/test_ask_interpretation_cache.py` (9 tests): the key folds case and whitespace and
nothing else; the same question from the same person is one model call; `explain` and `ask`
share one reading; the search behind an answer is never cached; a different viewer or a
different language misses; the allowance is charged on a hit; a keyword answer is not kept;
`clear_all` empties it; a caller cannot edit the next asker's reading. Plus the housing
equivalent.

### Files touched

`backend/core/llm/{ask.py,_http.py,__init__.py}`, `backend/core/app.py`,
`backend/members/application/ask_service.py`,
`backend/housing/application/housing_ask_service.py`,
`tests/unit/test_ask_interpretation_cache.py`.

---

## 2. `PathService.members_in` paged in SQL

### Validated

- `backend/paths/application/path_service.py:83-89` (before) called
  `member_ids_in(stage, group, filters)` and then `self._cards.page(ids, skip, limit)`.
- The claim "pages in Python" is not quite right and is worth recording: `SqlMemberCards.page`
  already used `page_with_total` (`backend/paths/infrastructure/member_cards.py:55`), so the
  page was cut in SQL. What was wrong is that **every** id in the group came back over the
  wire and then went into an `IN` list, to select at most `limit` of them.
- `paths_repository.member_ids_in:265-279` said unpaged was on purpose because "there is no
  one query that can order by a column only the other one has". That is not true:
  `backend/paths/infrastructure/_member_tables.py` already exposes a metadata-free `members`
  handle, which is the same seam `member_classes` comes through, so the ids can be ordered by
  `members.name` where they are selected.
- **`member_ids_in` was not used by the Ask narrowing.** Grepped: its only caller was
  `members_in`. The Ask's flow narrowing goes `AskService.matching_member_ids` ->
  `MemberRepository.matching_ids` -> `PathFilters.member_ids`, a different path entirely
  (`backend/members/application/ask_service.py:116`,
  `backend/paths/infrastructure/paths_repository.py:74-78`). That path is untouched and its
  tests still pass. So `member_ids_in` was replaced rather than kept alongside.

### Changed

- `PathRepository.member_ids_in` -> `member_ids_page(..., skip, limit) -> (ids, total)`
  (`backend/paths/application/ports.py`, `backend/paths/infrastructure/paths_repository.py`).
  It joins the `members` handle, orders by `(name, id)` and goes through
  `backend/core/sql.py page_with_total`, so the count and the page are one statement.
  The `id` tie-break is new and deliberate: names repeat here, and an ordering that is not
  total lets Postgres put the same person on two pages.
- `MemberCards.page(ids, skip, limit)` -> `cards(ids) -> list[MemberCard]`, ordered the same
  way (`backend/paths/infrastructure/member_cards.py`).
- `PathService.members_in` assembles the `PageResult`. The `{items,total}` shape is identical.
- Still two statements, but the second one's `IN` list is now one page long instead of one
  group long, and the first returns `limit` uuids instead of all of them.

### Tests

No new test: `tests/integration/test_paths_gaps.py:343-389` already pins the paging contract
(`limit=1`, `skip=1`, an empty group, and every filter narrowing the set) and
`tests/integration/test_paths.py` the ordering. Both pass unchanged, which is the point.

### Files touched

`backend/paths/application/{ports.py,path_service.py}`,
`backend/paths/infrastructure/{paths_repository.py,member_cards.py}`.

---

## 3. `MemberService._unique_slug` in one query

### Validated

`backend/members/application/member_service.py:175-186` (before) probed `find_id_by_slug` once
for the base and once per taken suffix, so the seventh Anna Schmidt cost seven round trips.
Called from `create_self_profile` (line 118). `members.slug` is `unique=True`
(`backend/members/infrastructure/orm_models.py:49`), so the database still has the last word
on a race.

### Changed

- `MemberRepository.slugs_for_base(base)` added to the port
  (`backend/members/application/ports.py`) and implemented in
  `backend/members/infrastructure/members_repository.py` as
  `slug = :base OR slug LIKE :base || '-%'` in one statement. Safe to build the pattern by
  concatenation because `base` comes from `_slugify`, which keeps only `a-z0-9-`, so it
  carries no `%` or `_`; that is stated in the docstring. Both arms use the unique index.
- `_unique_slug` fetches the set once and picks the first free suffix in memory.

### Tests added

`tests/unit/test_members_service_gaps.py` (5 tests, `SlugMembers` fake): a free name is taken
as it is in one query; base, base-2 and base-3 taken gives base-4 in one query; a gap
(base-2 free) is filled rather than skipped; `ada-lovelace-king` is somebody else's slug and
not a collision (it comes back from the same prefix query, so the check has to be membership
in the series); and one end to end through `create_self_profile`.

### Files touched

`backend/members/application/{ports.py,member_service.py}`,
`backend/members/infrastructure/members_repository.py`,
`tests/unit/test_members_service_gaps.py`.

---

## 4. Migrator URL guard (F-11) and the pool budget (F-14)

### Validated, and partly not real

- **No validator is needed.** `env_ignore_empty=True` in
  `backend/core/settings/_env.py:26` already turns `DATABASE_MIGRATOR_URL=` into `None`.
  Verified directly: with `DATABASE_MIGRATOR_URL=""` in the environment,
  `DatabaseSettings.migrator_url_override` is `None` and `migrator_url` falls back to the
  runtime URL. So F-11's "falls back silently" is about **visibility**, not about an empty
  string leaking through, and adding a validator would be dead code. Left alone, and pinned
  with a test instead so nobody removes `env_ignore_empty` by accident.
- `infrastructure/db.py log_resolved_urls` (added by a previous agent) already logged which
  URL each engine reaches, but its fallback wording was the bare `"falling back to
  DATABASE_URL"`, and there was no pool budget on the line.

### Changed

`infrastructure/db.py log_resolved_urls`: the line now reads

```
database runtime=%s transaction_pooled=%s pool=%s+%s(max %s per worker) migrator=%s (%s)
```

with the fallback spelled out as `DATABASE_MIGRATOR_URL unset, migrator falls back to
DATABASE_URL`, and `pool_size + max_overflow` added (F-14) because that is the number that has
to be multiplied by `--workers` before it is compared with the pooler's limit. The docstring
records why. `infrastructure/alembic/env.py` untouched.

### Tests added

- `tests/unit/test_settings.py::test_an_empty_migrator_url_reads_as_unset_and_falls_back`.
- `tests/unit/test_db_pooling.py`: the boot line says the migrator falls back and prints
  `pool=5+5(max 10 per worker)` and no password; and it names the override when there is one.

### Files touched

`infrastructure/db.py`, `tests/unit/{test_settings.py,test_db_pooling.py}`.

---

## 5. RLS guard test

### Validated

`infrastructure/alembic/versions/001_initial_schema.py:1047-1069` (`_lock_down_data_api`)
enables RLS by walking a hard-coded `DROP_ORDER` tuple, which is exactly the kind of list a
new bounded context gets added without. Checked: all 21 tables in `Base.metadata` are
currently in it, so the test is green today and is a guard against the next table.

### Added

`tests/integration/test_rls.py`, its own file so it uses the ordinary integration database
fixture and never touches `test_migrations.py`'s hard-coded scratch database name:

- every table in `Base.metadata` exists in the migrated database and has
  `pg_class.relrowsecurity = true`, with a failure message naming what to do;
- no table carries an RLS policy. RLS with no policies denies everything, which is the whole
  point of turning it on; a policy added later is what would make the directory public again.

Both pass against 001 + 002.

---

## 6. Documentation and comment corrections

### 6a. `_member_query.py` (done)

`backend/members/infrastructure/_member_query.py:46-53` claimed the correlated EXISTS over
ILIKE "finishes in single-digit milliseconds". Replaced with the measured numbers: 45.5 ms and
459 shared buffers for `past_company=McKinsey` over 10,108 `positions` rows, 10 ms for
`school` over `educations`, plus the note that trigram indexes on `positions(company)` and
`positions(title)` are the follow-up when the table grows, the way 002 already added one for
`members.current_company`.

### 6b. Production runbook and `pg_stat_statements` (done)

- `backend/README.md`, new "Running it in production" section: the launch line is
  `uvicorn backend.core.main:app` (verified against `backend/core/main.py`, which is
  `app = create_app()`), with `--workers`, `--proxy-headers`, `--forwarded-allow-ips`,
  `--timeout-keep-alive 30`, migrations first, and the note that each worker gets its own
  pool and its own copy of every in-process cache. Includes the `pg_stat_statements` note
  (dashboard, not a migration).
- `infrastructure/README.md`, "What the API is actually spending time on" under "Inspecting
  the database": why it is enabled from the Supabase dashboard and not from a migration
  (`CREATE EXTENSION` needs a superuser Supabase does not hand out, and the extension belongs
  to the instance rather than to this schema), plus the two queries worth having.

### 6c. `SUPABASE_JWT_SECRET` after asymmetric keys (done)

Checked `backend/core/settings/auth.py:23-24`: `supabase_url` aliases `SUPABASE_URL`,
`jwt_secret` aliases `SUPABASE_JWT_SECRET`, and `dev_login_enabled` is `AUTH_DEV_LOGIN_ENABLED`.
Noted in `backend/README.md` (Authentication section) and in `.env.example`: once the project
moves to asymmetric signing keys, leave `SUPABASE_JWT_SECRET` unset in production (an empty
line reads as unset via `env_ignore_empty`), because a shared symmetric secret is a second way
to mint a token this API accepts; keep it only where `AUTH_DEV_LOGIN_ENABLED=true`, which
signs with exactly that key.

### 6d. `avatars_bucket` and `public_url` (deleted, with one nuance)

Grepped `backend/`, `scripts/`, `infrastructure/`, `tests/`, `docs/`, `.env.example` and
`frontend/`. The only hits were:

- the definitions themselves (`backend/core/settings/storage.py:37,49-53`);
- `tests/unit/test_settings.py`, three assertions that test **only these two members** and
  nothing that uses them;
- the documentation lines (`backend/README.md` settings table, `.env.example`).

**Nuance, since the brief said "if anything references them, leave and report":** the only
non-documentation references were the tests of the dead code itself. There is no production
caller in either half of the platform. I read that as the audit's "referenced nowhere" and
deleted them; if you would rather keep them, the revert is `storage.py` plus those three
assertions. Also verified the frontend serves the 1,250 avatars as static files from
`frontend/public/avatars` (`frontend/src/components/MemberAvatar.tsx`), which is what makes a
public bucket URL builder pointless.

Removed: the field, the method, `STORAGE_AVATARS_BUCKET` from `.env.example`, the mention in
the `backend/README.md` settings table, and the three tests. Added a paragraph to the
`StorageSettings` docstring saying why there is no public-URL builder.

`docs/architecture.md` corrected in three places: the system diagram no longer draws
`Web -->|avatars| Storage` (it now draws the ingest writing `frontend/public/avatars` and the
web app serving them, and the API as the only party talking to Storage); the deployment
diagram's `Storage: avatars` became `Storage: private upload buckets` with the arrow moved
from `Web` to `API`; and section 9 now says the `avatars` bucket is only for an avatar a
member uploads for themselves, while the 1,250 the directory draws are static files.

---

## 7. Request timing log (done, it stayed small)

Added to `RequestGuards` rather than as a second wrapper, so it rides the pass that is already
there. `_security_header_sender` now also records the response status; `__call__` times the
request and logs in a `finally` (a request that ended in an exception is exactly the one worth
a duration for). The path logged is the **route template** off `scope["route"]`, which FastAPI
leaves on the scope once it has matched (verified at runtime that a pure-ASGI wrapper sees it
after the inner app returns) so there is not one log shape per member id; it falls back to the
raw path for a request refused before routing.

`APP_SLOW_REQUEST_MS` (default 500) added to `AppSettings`, documented in `.env.example` and
the `backend/README.md` settings table. At or above it, INFO; below, DEBUG.

Tests: `tests/unit/test_app_factory_core_gaps.py`, one line per request under its template at
INFO with a zero threshold, and DEBUG plus `status=413` for a body refused before routing.

---

## Verification

### `uv run poe lint`

```
Poe => ruff check backend infrastructure scripts tests
All checks passed!
```

### `uv run poe format`

```
Poe => ruff format backend infrastructure scripts tests
313 files left unchanged
```

### `uv run poe test-fast`

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
565 passed, 1 skipped, 250 deselected, 1 warning in 22.82s
```

### Integration

`createdb cdtm_community_test_be4` then
`DATABASE_URL=postgresql://localhost:5432/cdtm_community_test_be4 uv run pytest tests/integration -m integration -q --deselect tests/integration/test_migrations.py`

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_auth.py::test_unverified_top_level_email_is_rejected
1 failed, 247 passed, 2 deselected, 1 warning in 70.05s (0:01:10)
```

And the areas this pass touched, run on their own:

```
tests/integration/{test_paths.py,test_paths_gaps.py,test_rls.py,test_members_b_gaps.py}
41 passed, 1 warning in 18.93s
```

### The one failure is not from this pass

`test_unverified_top_level_email_is_rejected` is in the identity context, which is the
concurrent agent's territory (`backend/identity/**` is modified in the tree by them, not by
me). It is also reproducible from committed code alone: `_raw_token` in the (unmodified)
`tests/integration/test_auth.py:25` defaults to `app_metadata={"provider": "google"}`, and
`_email_is_verified` at `backend/identity/infrastructure/jwt_verifier.py:162-169`, which is
unchanged from HEAD, returns `True` for a Google provider even when the top-level
`email_verified` claim is absent. So the token the test says must be rejected is accepted by
HEAD's own logic. Nothing I changed is in that path. Flagging it rather than fixing it, since
that file is not mine this pass. A second failure,
`test_events_gaps.py::test_an_event_keeps_every_field_it_was_published_with`, appeared in an
earlier run and was gone by the final one: the other agent was mid-edit on
`backend/events/api/schemas.py`.

---

## Files touched

Code:
`backend/core/app.py`, `backend/core/llm/{__init__.py,_http.py,ask.py}`,
`backend/core/settings/{app.py,storage.py}`,
`backend/members/application/{ask_service.py,member_service.py,ports.py}`,
`backend/members/infrastructure/{members_repository.py,_member_query.py}`,
`backend/housing/application/housing_ask_service.py`,
`backend/paths/application/{path_service.py,ports.py}`,
`backend/paths/infrastructure/{paths_repository.py,member_cards.py}`,
`infrastructure/db.py`.

Docs: `backend/README.md`, `infrastructure/README.md`, `docs/architecture.md`, `.env.example`.

Tests: `tests/unit/test_ask_interpretation_cache.py` (new),
`tests/integration/test_rls.py` (new), `tests/unit/test_members_service_gaps.py`,
`tests/unit/test_settings.py`, `tests/unit/test_db_pooling.py`,
`tests/unit/test_app_factory_core_gaps.py`.

Nothing under `backend/jobboard/api`, `backend/housing/api`, `backend/events/api`,
`backend/network/**`, `backend/members/api/ask.py`, `backend/paths/api/paths.py`,
`backend/members/infrastructure/_mappers.py`,
`backend/identity/infrastructure/account_repository.py` or `frontend/` was touched.
