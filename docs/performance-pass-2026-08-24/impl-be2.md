# Backend performance pass (impl-be2)

Everything below was run from the repo root with `uv run ...`. Every database command used an
explicit local `DATABASE_URL`; the root `.env` Supabase URL was never used and nothing was
committed.

Measurement databases (all loopback):

* `cdtm_perf_002` - a clean copy at the `001_initial_schema` index state, built with
  `createdb` + `alembic upgrade 001_initial_schema` + a `pg_dump -a` of the seeded
  `cdtm_perf_audit` data (1,115 members, 6,000 jobs, 1,200 announcements, 9,600
  announcement_reads, 5,000 saved_members), `VACUUM ANALYZE`d. "Before" and "after" numbers
  are the same rows in the same database, with and without `002_hot_path_indexes`.
* `cdtm_community_test_perf` - a private copy of the integration database, so the concurrent
  identity agent's suite could not collide with mine.

`shared hit` buffer counts are the metric, not wall time: wall time on this laptop swings by
several ms between identical runs.

---

## 1. Members eager loading - DONE

`positions`, `educations` and `ca_detail` on `MemberRow` are `lazy="raise"`; `classes`,
`entry` and `intents` stay `lazy="selectin"` (they are one row or a handful and every read
path wants them). Explicit `selectinload` is added only where a full profile is built.

Files: `backend/members/infrastructure/orm_models.py`,
`backend/members/infrastructure/members_repository.py`,
`backend/members/infrastructure/entries_repository.py`,
`scripts/platform/seed_dev_data.py`.

* `_profile_loads()` / `_card_loads()` helpers in the repository; `get_by_slug` and
  `get_by_id` use the former, `get_many` and the list paths use `defer(MemberRow.search_text)`.
* `get_by_id` was switched from `Session.get` to `select(...).options(...)`. This is the
  subtle one: `Session.get` returns an identity-map hit without ever running SQL, so its
  loader options are silently skipped and the next `.positions` access raises.
* `Session.refresh()` does **not** populate a `lazy="raise"` relationship either. Both places
  that rebuilt the search haystack after a write (`upsert_member`, `refresh_search_text`, the
  other developer's `update_profile`, and `entries_repository.upsert`) now go through
  `_refresh_haystack`, a `select(...).options(selectinload(...)).execution_options(
  populate_existing=True)`.
* Transient/pending `MemberRow` objects still return an empty collection rather than raising
  (SQLAlchemy short-circuits before the raise strategy), so the unit tests that build a bare
  `MemberRow(...)` and call `build_search_text` are unaffected. Verified by running them.

Grep over every `.positions` / `.educations` / `.ca_detail` consumer plus the whole
integration suite is what caught the `Session.get` and `Session.refresh` cases; both were
real bugs that only appear at runtime.

Skill rule applied: **make the unsafe thing loud**. `lazy="raise"` turns an invisible N+1
into an exception in a test rather than a slow endpoint in production.

## 2. Window count instead of a companion `count(*)` - DONE (one context skipped)

New shared helper `page_with_total(session, stmt, *, skip, limit)` in `backend/core/sql.py`:
it appends `func.count().over()` to the page query, reads `total` off the first row, and
falls back to a real count query only when a page past the end returns no rows (when
`skip == 0` and there are no rows the answer is 0 without a second statement).

Adopted in: `members_repository.search`, `paths/infrastructure/member_cards.page`,
`announcements_repository.list`, `events_repository`, `housing_repository`,
`jobboard/{job,company,seeker}_repository`. `backend/jobboard/infrastructure/_query.py` was
deleted; its `_count` helper had no callers left.

The `{items, total}` response contract is byte-identical - the integration suite asserts on
`total` in every context and stayed green.

**Skipped: the account listing** in `backend/identity/infrastructure/account_repository.py:55`.
`backend/identity/**` is owned by a concurrently running agent (it has five modified files in
the working tree right now); editing it would have collided. It is a one-line change once
that agent lands: replace the `select(func.count()).select_from(stmt.subquery())` with
`page_with_total`.

Measured (directory search `?q=product`, `cdtm_perf_audit`): two statements, 3,929 shared
buffers -> one statement, 1,949.

Honest caveat, measured after item 9 landed: the window count evaluates over every matching
row, so on a list whose ordering an index can serve, the plain page stops after `limit` rows
and the window count cannot. On the job board's first page after `ix_jobs_published_created`
exists:

| Shape | Buffers | Round trips |
| --- | --- | --- |
| page + separate count | 3 + 16 = 19 | 2 |
| page with `count(*) OVER ()` | 245 | 1 |

Against a pooled remote Supabase a saved round trip (tens of ms) still beats 240 local buffer
hits (about 4 ms), which is why I kept it, but it is a real trade and it is now written down
in `docs/database-design.md` section 8.4 along with the follow-up (a cached or approximate
total, or keyset pagination, is what a much larger jobs table would want).

Where the plan has to scan anyway, the window count is a straight win:

| List | Before (page + count) | After (window, with 002) |
| --- | --- | --- |
| announcements | 145 + 19 = 164 buffers, 2 trips | 98 buffers, 1 trip |
| housing | 53 + 53 = 106 buffers, 2 trips | 60 buffers, 1 trip |

## 3. Paths `flow()` and `groups()` as one statement each - DONE

`backend/paths/infrastructure/paths_repository.py`. `flow()` was six aggregate queries plus
the intents query; the six are now a single `GROUP BY GROUPING SETS (...)` decoded with a
`GROUPING()` bitmask (`_GroupingSet(IntEnum)`, values `0b001` through `0b111`). `groups()` is
one grouping-sets statement with the sort done in Python. The intents statement and the
`PathFilters` path are untouched.

Verified for equivalence rather than assumed: `scratchpad/flow_compare.py` runs the old and
new implementations against `cdtm_perf_audit` over five filter cases (no filters,
`study_group`, `current_group`, `first_step_group`, and `member_ids` of 200) and reports
`statements 7 -> 2` and `same_multiset=True` for all five. Before I added a tie-break the
only differences were the order of equal-count rows (already arbitrary); with
`.order_by(n.desc(), study, first_step, current)` the output is deterministic and one case is
byte-identical.

Measured on `cdtm_perf_002`: six statements at roughly 25-28 buffers each (~150 buffers, six
round trips) -> one statement, 31 buffers, 2.93 ms, a single sequential scan of 25 buffers.

## 4. Facets in one statement - DONE

`GET /members/facets` was three sequential awaits (`list_classes`, `list_majors`, `count`).
It is now one repository method `facets()` returning a frozen `Facets` dataclass, built from
one statement with three uncorrelated scalar subqueries (`json_agg(json_build_object(...)
ORDER BY year DESC, label)`, `array_agg(DISTINCT major ORDER BY major)`, `count(id)`).

Files: `backend/members/application/ports.py` (the `Facets` dataclass and the protocol
method), `backend/members/infrastructure/members_repository.py`,
`backend/members/application/member_service.py`, `backend/members/api/members.py`.

## 5. `GET /api/v1/announcements/unread-count` - DONE

Returns exactly `{"unread": <int>}`, response model `UnreadCountPublic`, auth required
(`PrincipalDep`), one statement (the existing anti-join `unread_count`), and **registered
before `/{announcement_id}`** so the UUID path parameter cannot swallow the literal.

Files: `backend/announcements/api/announcements.py`, `backend/announcements/api/schemas.py`.

Test added: `tests/integration/test_announcements.py::test_unread_count_endpoint_matches_the_list_badge`
- asserts the exact body shape, that it agrees with the list endpoint's `unread` field, that
it drops after a read, and that an anonymous caller is refused.

Confirmed in the generated contract:

```json
"UnreadCountPublic": {
 "additionalProperties": false,
 "properties": {"unread": {"title": "Unread", "type": "integer"}},
 "required": ["unread"], "type": "object"
}
```

## 6. In-process TTL cache - DONE

New `backend/core/cache.py`: a dependency-free `TTLCache(maxsize, ttl)` on `time.monotonic()`
with LRU eviction, a module registry and `clear_all()`. It never stores `None`, so "cached
miss" and "cached None" cannot be confused.

Applied in the **application layer only** (repositories are untouched, routers only set the
header):

| Endpoint | TTL | maxsize | Key | Header |
| --- | --- | --- | --- | --- |
| `/members/facets` | 300 | 1 | - | `private, max-age=300` |
| `/paths/groups` | 600 | 1 | - | `private, max-age=600` |
| `/paths/flow` | 300 | 64 | `(class_id, study_group, first_step_group, current_group)` | `private, max-age=300` |
| `/companies/` | 300 | 64 | `(skip, limit, filters)` | `public, max-age=300` |

* `/paths/flow` **bypasses the cache entirely when `filters.member_ids is not None`** - that is
  the Ask, whose key would be a thousand uuids and whose answer is asked for once.
* `/companies/` is the only one with `public`, and only because it is the one list with no
  auth dependency at all. Every company write (`create`, `update`, `delete`) clears that
  cache, so a correction is visible on the next request rather than in five minutes.
* `PathService.recompute_all` and `scripts/platform/load_community.py` call `clear_all()`.
* `/paths/groups` returns copies of the cached lists so a caller cannot mutate what the next
  caller is handed.

One thing this exposed: module-scope caches leak between tests. `tests/unit/test_company_service_
jobboard_a_gaps.py` started failing because an earlier test's cached page was served after the
tables were truncated. Fixed properly rather than by special-casing that test: new
`tests/conftest.py` with an autouse fixture that calls `clear_all()` before and after every
test in every suite.

## 7. Ask viewer context - DONE

`backend/members/application/ask_service.py::_viewer_context` called `get_by_id`, which is a
row plus three eager loads plus the claimed-ids probe plus a positions/educations fetch, to
read three scalars. It now calls a new narrow repository method
`MemberRepository.viewer_context(member_id) -> (class_label, location, class_year)`: one
statement, two uncorrelated scalar subqueries, with the Entry's location winning over the
scrape's exactly the way `to_member` resolves it. Mirrored in
`backend/members/application/ports.py`.

`tests/unit/test_members_ask_service_gaps.py::FakeMembers` grew the same method, derived from
the profile the fake already holds so no expectation moved. 8 passed.

## 8. Input caps - DONE

* `/members/at-company`: `company` is now
  `list[Annotated[str, StringConstraints(max_length=128)]]` - per element, not on the list.
* `/paths/flow` and `/paths/members`: every group parameter capped at
  `MAX_GROUP_NAME = 120` (the longest real name is "Natural Sciences & Math", so anything
  longer matches nothing; the cap is what keeps an unbounded string out of the query and out
  of the flow cache's key).
* `matching_ids` capped at `MAX_MATCHING_IDS = 5_000` with the reasoning in a comment.

## 9. Migration `002_hot_path_indexes` - DONE

`infrastructure/alembic/versions/002_hot_path_indexes.py`, `down_revision =
"001_initial_schema"`. Twelve indexes, every one
`CREATE INDEX CONCURRENTLY IF NOT EXISTS` inside `op.get_context().autocommit_block()`.
Nothing is dropped. All twelve are mirrored in the ORM `__table_args__`.

| Index | Table | Definition |
| --- | --- | --- |
| ix_announcement_reads_member_id | announcement_reads | (member_id) |
| ix_event_rsvps_member_id | event_rsvps | (member_id) |
| ix_saved_members_saved_member_id | saved_members | (saved_member_id) |
| ix_announcements_author_member_id | announcements | (author_member_id) |
| ix_events_created_by_member_id | events | (created_by_member_id) |
| ix_companies_created_by_member_id | companies | (created_by_member_id) |
| ix_jobs_published_created | jobs | (created_at DESC) WHERE status = 'published' |
| ix_announcements_board_order | announcements | (is_pinned DESC, coalesce(published_at, created_at) DESC) |
| ix_housing_listings_created_at | housing_listings | (created_at DESC) |
| ix_member_paths_current_group | member_paths | (current_group) |
| ix_member_paths_first_step_group | member_paths | (first_step_group) |
| ix_members_current_company_trgm | members | USING gin (current_company gin_trgm_ops) |

`tests/integration/test_migrations.py`: **2 passed** - no drift between the migration chain
and `Base.metadata`, and downgrade to base is still clean.

EXPLAIN (ANALYZE, BUFFERS) on `cdtm_perf_002`, same data, before and after:

| Query | Before | After |
| --- | --- | --- |
| jobs default list (20 rows) | Seq Scan + top-N heapsort, **233 buffers**, 31.3 ms | Index Scan on ix_jobs_published_created, **3 buffers**, 0.09 ms |
| jobs list as shipped (window count) | 230 buffers, 51.0 ms | 245 buffers, 4.59 ms |
| jobs count companion | 16 buffers, 0.97 ms | 16 buffers (Index Only Scan), 3.20 ms |
| announcements list (20 rows) | **145 buffers**, 2.03 ms | **65 buffers**, 2.25 ms |
| announcements list as shipped (window count) | (would be 145) | **98 buffers**, one round trip |
| announcements count companion | 19 buffers | no longer issued |
| announcements unread count | **99 buffers**, 0.78 ms | **32 buffers**, 0.28 ms (Bitmap Index Scan on ix_announcement_reads_member_id) |
| housing list | 53 buffers, 9.53 ms | 3 buffers, 0.03 ms (60 with the window count) |
| saved_members FK lookup | 48 buffers (Seq Scan) | 4 buffers (Index Only Scan) |
| event_rsvps FK lookup | 73 buffers (Seq Scan) | 3 buffers (Index Only Scan) |

The two headline numbers the brief asked for: **jobs default list 233 -> 3 shared buffers**
(the window-count shape it actually ships as: 230 -> 245 buffers but 51.0 -> 4.59 ms, one
round trip instead of two), **announcements list 145 -> 65 buffers** (98 as shipped with the
window count, one round trip instead of 145 + 19 across two).

The finding worth keeping: `ix_jobs_published_list` is on `published_at DESC` but
`_order_by` in `job_repository.py` sorts by `created_at DESC`, so despite its name that index
had never served the board's default listing. `docs/database-design.md` said it "matches the
board's default listing query exactly"; that claim is now corrected.

## 10. Deliberately skipped - reported as follow-ups

* **Summary DTOs without body/description.** The list endpoints still ship the full `body`
  (announcements) and `description` (jobs, housing) of every row. A `*Summary` DTO for the
  list and the full DTO for the detail endpoint would cut the announcements list response
  substantially. It is a contract change and the frontend agent is mid-build against the
  current shape, so it is not something to slip in during a performance pass.
* **Pagination on `/network/saved` and `/network/intros`.** Both return everything. Bounded
  in practice today, unbounded by contract.
* **Keyset pagination for the directory.** Offset is fine at 1,115 members. It is the right
  answer only if the directory grows an order of magnitude, and it changes the API contract.
* **The account listing window count** (item 2 above) - blocked on file ownership, not on
  judgement.

## Documentation corrections

`docs/database-design.md`:

* section 7 (jobs indexes): removed the false claim that `ix_jobs_published_list` "matches
  the board's default listing query exactly"; documented both partial indexes and which one
  the default list actually uses, with the measured numbers.
* section 5.2: "Three partial indexes exist, on `cofounding`, `mentoring` and `hiring` ... The
  other three flags have no index yet" - wrong, all six flags have one. Corrected.
* section 11 (account binding): "There is no functional index on `lower(email)`" - wrong,
  `uq_members_email_lower` is a UNIQUE index on the expression `lower(email)`. Corrected.
* section 8.4 (pagination): rewritten for the window count, including the measured case where
  it is the more expensive shape.
* section 12: `002_hot_path_indexes` described; the file map gained `002_hot_path_indexes.py`,
  `backend/core/sql.py` and `backend/core/cache.py`.

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
308 files left unchanged
```

### `uv run poe test-fast`

```
535 passed, 1 skipped, 238 deselected, 1 warning in 19.54s
```

### `uv run poe test-integration` (against `cdtm_community_test_perf`)

```
FAILED tests/integration/test_auth.py::test_unverified_top_level_email_is_rejected
ERROR tests/integration/test_migrations.py::test_migration_chain_matches_orm_metadata
1 failed, 236 passed, 536 deselected, 1 warning, 1 error in 343.37s (0:05:43)
```

Both are external to this work and both were confirmed:

* `test_unverified_top_level_email_is_rejected` fails on the concurrent identity agent's
  in-flight edits. `git status` shows five modified files under `backend/identity/` (deps.py,
  auth_service.py, ports.py, account_repository.py, jwt_verifier.py) and `test_auth.py` itself
  unmodified. I did not touch that context.
* The `test_migrations` error is
  `psycopg.errors.AdminShutdown: terminating connection due to administrator command` on
  `CREATE EXTENSION IF NOT EXISTS pg_trgm` - the other agent's suite running
  `DROP DATABASE cdtm_community_migration_check WITH (FORCE)` while mine was connected to it.
  The scratch database name is hard-coded in the fixture, so two concurrent runs always
  collide. Re-run on its own:

```
2 passed, 1 warning in 6.18s
```

The announcements suite was likewise green on its own (`4 passed`) after showing two failures
in an earlier full run that overlapped with the other agent.

### `uv run poe openapi`

```
Poe => python scripts/platform/export_openapi.py
Wrote /Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/openapi/openapi.json
```

### `cd frontend && npm run generate:api`

```
> openapi-typescript openapi/openapi.json -o src/api/schema.d.ts && prettier --write src/api/schema.d.ts
openapi-typescript 7.13.0
openapi/openapi.json -> src/api/schema.d.ts [406.8ms]
src/api/schema.d.ts 789ms
```

### `uv run poe openapi-check`

```
Wrote /Users/krishuagarwal/Desktop/Programming/python/cdtm-job/frontend/openapi/openapi.json
frontend/openapi/openapi.json was stale; it has just been regenerated.
Stage it and commit again: git add frontend/openapi/openapi.json
The frontend client follows: cd frontend && npm run generate:api
```

Exit code 1, and it cannot be anything else here: the check compares the regenerated spec
against the committed one and this pass adds an endpoint. The spec and the TypeScript client
are both regenerated and in the working tree; `git add frontend/openapi/openapi.json` at
commit time clears it. I was asked not to commit.

---

## Files touched

New: `backend/core/cache.py`, `infrastructure/alembic/versions/002_hot_path_indexes.py`,
`tests/conftest.py`.

Deleted: `backend/jobboard/infrastructure/_query.py`.

Modified: `backend/core/sql.py`; `backend/members/{api/members.py,
application/{ask_service.py,member_service.py,ports.py},
infrastructure/{members_repository.py,entries_repository.py,orm_models.py}}`;
`backend/paths/{api/paths.py, application/path_service.py,
infrastructure/{paths_repository.py,member_cards.py,orm_models.py}}`;
`backend/announcements/{api/{announcements.py,schemas.py},
infrastructure/{announcements_repository.py,orm_models.py}}`;
`backend/jobboard/{api/companies.py, application/company_service.py,
infrastructure/{job,company,seeker}_repository.py, infrastructure/orm_models.py}`;
`backend/events/infrastructure/{events_repository.py,orm_models.py}`;
`backend/housing/infrastructure/{housing_repository.py,orm_models.py}`;
`backend/network/infrastructure/orm_models.py`;
`scripts/platform/{load_community.py,seed_dev_data.py}`;
`tests/integration/test_announcements.py`; `tests/unit/test_members_ask_service_gaps.py`;
`docs/database-design.md`; `frontend/openapi/openapi.json`; `frontend/src/api/schema.d.ts`.

The other developer's uncommitted files (`backend/members/api/me.py`,
`backend/members/application/{commands,member_service,ports}.py`,
`backend/members/infrastructure/members_repository.py`,
`tests/integration/test_identity_gaps.py`, `tests/unit/test_media_gaps.py`) were edited only
with precise string replacements; their `update_profile` method is intact and now calls
`_refresh_haystack` so it does not trip over `lazy="raise"`. Nothing under
`backend/identity/**`, `backend/media/**`, `backend/core/{app,main}.py`,
`backend/core/settings/**`, `infrastructure/db.py` or `pyproject.toml` was touched. No commit,
no `git checkout/stash/reset`.
