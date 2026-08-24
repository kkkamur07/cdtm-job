# Postgres schema, index and connection audit: CDTM Community platform

Repo `/Users/krishuagarwal/Desktop/Programming/python/cdtm-job`, branch `master`.
Read-only on the repo; every artefact below lives in the scratchpad or in a throwaway local database.

## Skill rules applied

Base dir `/Users/krishuagarwal/.claude/skills/supabase-postgres-best-practices/`.
`references/_sections.md` plus **all 32 rule files** were read. The task named some rules that do not
exist under those filenames; the actual set is:

| Prefix | Files read |
| --- | --- |
| `query-` | `query-missing-indexes`, `query-partial-indexes`, `query-composite-indexes`, `query-covering-indexes`, `query-index-types` |
| `conn-` | `conn-pooling`, `conn-limits`, `conn-prepared-statements`, `conn-idle-timeout` |
| `schema-` | `schema-data-types`, `schema-primary-keys`, `schema-foreign-key-indexes`, `schema-constraints`, `schema-partitioning`, `schema-lowercase-identifiers` |
| `data-` | `data-batch-inserts`, `data-n-plus-one`, `data-pagination`, `data-upsert` |
| `lock-` | `lock-advisory`, `lock-deadlock-prevention`, `lock-short-transactions`, `lock-skip-locked` |
| `monitor-` | `monitor-explain-analyze`, `monitor-pg-stat-statements`, `monitor-vacuum-analyze` |
| `security-` | `security-rls-basics`, `security-rls-performance`, `security-privileges` |
| `advanced-` | `advanced-full-text-search`, `advanced-jsonb-indexing` |

Names the task used that map onto the above: `query-index-only-scans` and `query-covering-indexes` are
one file; `query-explain-analyze` is `monitor-explain-analyze`; `query-pagination`/`query-count` are
`data-pagination`; `query-n-plus-one` is `data-n-plus-one`; `conn-pool-sizing` is `conn-limits`;
`conn-statement-timeout` is covered by `lock-short-transactions`; `schema-text-search` is
`advanced-full-text-search`; `schema-jsonb` is `advanced-jsonb-indexing`; `data-batch` is
`data-batch-inserts`.

---

# 1. Measurement

## 1.1 Is there a database, and does it have data?

`pg_isready` -> `/tmp:5432 - accepting connections`. Local server is **PostgreSQL 14.22 (Homebrew)**.

The root `.env` `DATABASE_URL` is **not local**: it points at
`postgresql://postgres.lclpksfpymzblpgmntqe:REDACTED@aws-1-eu-north-1.pooler.supabase.com:5432/postgres`
(Supabase Supavisor, session-mode port). `DATABASE_MIGRATOR_URL` is set to the **empty string**.
Nothing was run against Supabase.

The local database the docs name, `cdtm_community`, exists but is **effectively empty**:

```
members 1 | positions 0 | member_paths 1 | jobs 0 | housing_listings 0 | accounts 1
```

`cdtm_community_test` has 1 member, `cdtm_attack` 11, `cdtm_review_scratch` 0.
`backups/internal_cdtm_public.sql.gz` is a dump of the **predecessor** database (drizzle,
`linkedin-persons`, `cms-users`), not this schema, so it is no use here.

So I built one. `frontend/public/data/index.json` plus 1,115 files in `frontend/public/profiles`
are present, so I created a throwaway database and ran the project's own migration and loader:

```bash
createdb cdtm_perf_audit
DATABASE_URL=postgresql://localhost:5432/cdtm_perf_audit \
  alembic -c infrastructure/alembic.ini upgrade head          # 001_initial_schema
DATABASE_URL=postgresql://localhost:5432/cdtm_perf_audit \
  uv run python scripts/platform/load_community.py \
    --index frontend/public/data/index.json --profiles frontend/public/profiles
# classes: 53 upserted / members: 1115 upserted / paths: 1115 recomputed
```

**Row counts (`members`, `positions`, `educations`, `member_classes`, `member_paths`, `classes`,
`ca_details` are REAL data produced by the repo's own loader):**

| Table | Rows | Source |
| --- | ---: | --- |
| `members` | 1,115 | real (loader) |
| `positions` | 10,108 | real |
| `educations` | 5,113 | real |
| `member_paths` | 1,115 | real (classifier) |
| `member_classes` | 1,012 | real |
| `classes` | 53 | real |
| `ca_details` | 31 | real |
| `jobs` | 6,000 | **synthetic** |
| `announcement_reads` | 9,600 | **synthetic** |
| `event_rsvps` | 7,200 | **synthetic** |
| `saved_members` | 5,000 | **synthetic** |
| `housing_listings` | 2,000 | **synthetic** |
| `intro_requests` | 2,000 | **synthetic** |
| `announcements` | 1,200 | **synthetic** |
| `events` | 600 | **synthetic** |
| `accounts` | 480 | **synthetic** |
| `member_intents` | 420 | **synthetic** |
| `member_entries` | 320 | **synthetic** |
| `companies` / `seekers` | 300 / 300 | **synthetic** |

The board tables have no real data anywhere in the repo, so I seeded them at plausible
one-to-two-year volumes. Every board finding below is labelled with which data it rests on.
`VACUUM ANALYZE` was run before measuring.

`select * from pg_extension` -> **`pg_trgm 1.6`, `plpgsql 1.0`**. `pg_stat_statements` is **not**
installed (`monitor-pg-stat-statements`).

**Caveat on timings.** This laptop is noisy: the identical `Seq Scan on members` for
`search_text ILIKE '%product%'` measured 35.8, 42.6, 63.0, 183.1 and 250.2 ms across five runs.
**`Buffers: shared hit` is deterministic and is the metric I rely on.** Times are given as
observed ranges.

## 1.2 How the exact SQL was obtained

A throwaway probe (`scratchpad/probe.py`) imports each repository, runs the hot path against
`cdtm_perf_audit`, and captures every statement through a SQLAlchemy `before_cursor_execute`
listener. Round-trip counts are therefore observed, not inferred.

| Repository call | Round trips | Wall (ms) |
| --- | ---: | ---: |
| `SqlMemberRepository.search(q="product")` | **9** | 300.7 |
| `SqlMemberRepository.search(skip=1000)` | **9** | 44.8 |
| `SqlMemberRepository.get_by_slug(...)` | **8** | 40.4 |
| `SqlMemberRepository.get_many(40 ids)` | **8** | 57.0 |
| `SqlMemberRepository.one_member_per_company(8 names)` | 1 | **203.2** |
| `SqlPathRepository.flow()` | **7** | 149.8 |
| facets (`list_classes` + `list_majors` + `count`) | 3 | 8.2 |
| `SqlHousingRepository.list` | 2 | 25.1 |
| `SqlJobRepository.list` | 2 | 23.6 |
| `SqlAnnouncementRepository.list` | 2 | 12.3 |
| `SqlAnnouncementRepository.unread_count` | 1 | 5.5 |
| `SqlNetworkRepository.list_saved` | 1 | 3.8 |
| `SqlMemberRepository.matching_ids(q)` | 1 | 35.6 |

The nine round trips on a directory page are: `count(*)` subquery, the page, then **six
`selectin` eager loads** (`classes`, `member_intents`, `member_entries`, `ca_details`,
`educations`, `positions`) fired by the relationships on `MemberRow`, then `_claimed_ids`.
`positions`, `educations` and `ca_details` are loaded and **thrown away**: `to_member`
(`backend/members/infrastructure/_mappers.py:32-55`) never reads them.

## 1.3 EXPLAIN (ANALYZE, BUFFERS) on the hot paths

### Directory list with search text (`members.search_text ILIKE '%q%'`)

The trigram GIN index **does work, for selective terms**:

```
-- search_text ILIKE '%mckinsey%'   (83 of 1,115 rows)
Bitmap Heap Scan on members  (actual time=0.295..1.691 rows=83 loops=1)
  Heap Blocks: exact=71   Buffers: shared hit=207
  ->  Bitmap Index Scan on ix_members_search_text_trgm (actual time=0.272 rows=83)
        Buffers: shared hit=13
Execution Time: 1.2 - 3.8 ms
```

For a **broad** term the planner correctly falls back to a seq scan, and the cost is the
`ILIKE` itself over a column whose average length is 1,186 bytes (max 5,319):

```
-- COUNT: search_text ILIKE '%product%'   (556 of 1,115 rows, est. 360)
Aggregate  (actual time=175.578..175.579 rows=1 loops=1)
  Buffers: shared hit=1972
  ->  Seq Scan on members  (cost=0.00..285.94 rows=360) (actual rows=556)
        Filter: (search_text ~~* '%product%'::text)
        Rows Removed by Filter: 559
        Buffers: shared hit=1972
Execution Time: 35.8 - 250.2 ms  (5 runs)

-- PAGE: same predicate + ORDER BY name ILIKE ... DESC, name LIMIT 20
Limit  (actual rows=20)  Buffers: shared hit=1957
  ->  Sort  Sort Key: ((name ~~* '%product%')) DESC, name
        Sort Method: top-N heapsort  Memory: 94kB
        ->  Seq Scan on members  (actual rows=556)  Buffers: shared hit=1949
Execution Time: 136 - 157 ms
```

**Total for one page: 3,929 shared buffers, the predicate evaluated twice, 2 round trips.**
Estimated 360 rows vs 556 actual: the default trigram selectivity estimate is off by 35%.

`count(*) OVER ()` in the same statement:

```
Limit ... ->  Sort ->  WindowAgg ->  Seq Scan on members
  Buffers: shared hit=1949          <- one scan, not two
Execution Time: 176 ms (same run-to-run band)
```

**1,949 buffers and 1 round trip instead of 3,929 and 2.**

### Deep offset vs keyset

```
-- OFFSET 1000 (page 51 of the 1,115-member directory)
Limit (actual rows=20)  Buffers: shared hit=272
  ->  Sort (actual rows=1020)  Sort Method: quicksort  Memory: 2249kB
        ->  Seq Scan on members (actual rows=1115)
Execution Time: 4.9 - 36.5 ms

-- keyset: WHERE (name, id) > (cursor) ORDER BY name, id LIMIT 20
Limit (actual time=1.141..1.145 rows=20)  Buffers: shared hit=39
  ->  Incremental Sort -> Index Scan using ix_members_name (actual rows=21)
Execution Time: 1.18 ms
```

**272 buffers -> 39, and a 2.2 MB in-memory sort disappears, already at 1,115 rows.**

### Members at company (`GET` "who works at X", `members_repository.py:126-162`)

The worst measured query in the codebase.

```
-- 8 company names, LATERAL, OR of two ILIKEs
Nested Loop  (actual time=119.849..616.007 rows=8 loops=1)
  Buffers: shared hit=22337
  ->  Values Scan on "*VALUES*" (rows=8)
  ->  Limit (actual time=76.987 rows=1 loops=8)
        ->  WindowAgg
              ->  Index Scan using ix_members_name on members
                    (actual time=10.650..76.842 rows=69 loops=8)
                    Rows Removed by Filter: 1046
                    Buffers: shared hit=22337
Execution Time: 616.204 ms
```

Eight loops x 1,115 rows x `current_company ILIKE` **or** `search_text ILIKE`.
`ix_members_search_text_trgm` cannot be used because the `OR` arm on `current_company` has no
index, so the planner has to walk the whole table per name.

### Paths flow (`GET /api/v1/paths/flow`)

Seven statements. Individually cheap on real data (1,115 `member_paths` rows):

```
[1] SELECT count(*) FROM (SELECT member_id FROM member_paths)         -- full scan
[2] GROUP BY study_group          [3] GROUP BY first_step_group
[4] GROUP BY current_group        [5] GROUP BY (study, first_step)
[6] GROUP BY (first_step, current)
[7] SELECT current_group, <6 intent bools> FROM member_paths LEFT JOIN member_intents
```

```
-- [6]
HashAggregate (actual time=1.439..1.512 rows=83)  Buffers: shared hit=25
  ->  Seq Scan on member_paths (actual rows=1031)
Execution Time: 1.6 ms

-- [7]  every row of member_paths shipped to Python
Hash Left Join (actual time=0.163..7.351 rows=1115 loops=1)  Buffers: shared hit=29
Execution Time: 7.4 ms
```

`ix_member_paths_groups (study_group, first_step_group, current_group)` was used by **none** of
them (`idx_scan = 0` afterwards): all six are full aggregates, and the two-column group-bys do
not need a leading-prefix index. Six full scans of the same table per request, ~150 ms wall.

### Facets (`GET /members/facets`, `backend/members/api/members.py:112-119`)

Three round trips, all cheap, all index-only:

```
-- DISTINCT major
Unique (actual time=0.076..0.174 rows=204)  Buffers: shared hit=5
  ->  Index Only Scan using ix_members_major on members  Heap Fetches: 0
Execution Time: 0.19 ms
-- count(members.id)
Index Only Scan using ix_members_major  Heap Fetches: 0  Buffers: shared hit=5   1.6 ms
```

Fine as-is. The only cost is the three round trips (see F-2).

### Housing list (synthetic, 2,000 rows)

```
-- city ILIKE '%Munich%' AND (expires_at IS NULL OR expires_at > now()) ORDER BY created_at DESC
Limit (actual rows=20)  Buffers: shared hit=56
  ->  Sort  Sort Key: created_at DESC   Sort Method: top-N heapsort
        ->  Seq Scan on housing_listings (actual rows=644)
              Rows Removed by Filter: 1356
              Buffers: shared hit=53
Execution Time: 2.8 ms
```

`ix_housing_listings_city_status (city, status)` was **not used** (`idx_scan = 0`) and cannot be:
the repository filters `city` with `ILIKE '%x%'` (`housing_repository.py:33`), not `=`.

### Jobs list (synthetic, 6,000 rows, 5,083 published)

```
-- status='published' ORDER BY created_at DESC LIMIT 20   (the board default)
Limit (actual time=87.504..87.509 rows=20)  Buffers: shared hit=230
  ->  Sort  Sort Key: created_at DESC   Sort Method: top-N heapsort  Memory: 35kB
        ->  Seq Scan on jobs (actual rows=5083)  Rows Removed by Filter: 917
              Buffers: shared hit=230
Execution Time: 87.542 ms

-- identical query but ORDER BY published_at DESC (what ix_jobs_published_list serves)
Limit (actual time=0.013..0.018 rows=20)  Buffers: shared hit=3
  ->  Index Scan using ix_jobs_published_list on jobs
Execution Time: 0.031 ms
```

**230 buffers vs 3; 87.5 ms vs 0.03 ms.** `docs/database-design.md:530` states the partial index
"matches the board's default listing query exactly". It does not: `_order_by` in
`job_repository.py:30-38` sorts on `created_at`, the index is on `published_at`.

### Announcements list + unread (synthetic, 1,200 announcements / 9,600 reads)

```
Limit (actual time=32.350..32.567 rows=20)  Buffers: shared hit=148
  ->  Sort  Sort Key: is_pinned DESC, (COALESCE(published_at, created_at)) DESC
        ->  Seq Scan on announcements (actual rows=1067)
  SubPlan 1  ->  Index Only Scan using pk_announcement_reads (loops=20)      -- fine
  SubPlan 3  ->  Seq Scan on announcement_reads
                   Filter: (member_id = '...')
                   Rows Removed by Filter: 9588
                   actual time=26.913..31.456   Buffers: shared hit=80       <- 95% of the query
Execution Time: 32.672 ms
```

`ix_announcements_published_at (published_at DESC)` cannot serve the sort
(`is_pinned DESC, coalesce(published_at, created_at) DESC`). The `is_read` flag is a seq scan of
`announcement_reads` because that table has no index on `member_id`.

`unread_count` is one query and a clean hash anti-join (1.3 ms) but pays the same seq scan.

### FK-side scans that `ON DELETE CASCADE` and the loader depend on

```
-- saved_members WHERE saved_member_id = ?   (5,000 rows)
Seq Scan on saved_members  Rows Removed by Filter: 4995  Buffers: shared hit=47   83.7 ms
-- event_rsvps WHERE member_id = ?           (7,200 rows)
Seq Scan on event_rsvps    Rows Removed by Filter: 7195  Buffers: shared hit=73   78.6 ms
-- announcement_reads WHERE member_id = ?    (9,600 rows)
Seq Scan on announcement_reads Rows Removed by Filter: 9588 Buffers: shared hit=80  1.6 ms
```

The skill's own detection query (`schema-foreign-key-indexes`) run against the live database:

```
        tbl         |        fk_col        |                  conname
--------------------+----------------------+-------------------------------------------
 announcement_reads | member_id            | fk_announcement_reads_member_id_members
 announcements      | author_member_id     | fk_announcements_author_member_id_members
 companies          | created_by_member_id | fk_companies_created_by_member_id_members
 event_rsvps        | member_id            | fk_event_rsvps_member_id_members
 events             | created_by_member_id | fk_events_created_by_member_id_members
 saved_members      | saved_member_id      | fk_saved_members_saved_member_id_members
```

### Other directory predicates, measured

| Predicate (`_member_query.py`) | Plan | Buffers | Time |
| --- | --- | ---: | ---: |
| `'ca' = ANY (roles)` (`:94`) | Seq Scan | 272 | 2.2 ms |
| `skills && ARRAY[...]` (`:156`) | Seq Scan | 410 | 4.0 - 55.8 ms |
| `location ILIKE '%Munich%'` (`:98`) | Seq Scan | 272 | 2.6 - 26.3 ms |
| `current_company ILIKE OR search_text ILIKE` (`:100-105`) | Seq Scan | 1,937 | 61.9 ms |
| `EXISTS positions.company ILIKE` (`:106-114`) | Seq Scan on positions (10,108 rows) | 459 | 45.5 ms |
| `EXISTS educations.school ILIKE` (`:127-135`) | Seq Scan on educations | 107 | 10.0 ms |
| `EXISTS member_paths.current_group = ?` (`:149`) | Seq Scan on member_paths | 35 | 1.2 ms |

### Index usage after the whole workload

`ix_housing_listings_city_status`, `ix_housing_listings_member_id`, `ix_jobs_company_id`,
`ix_jobs_posted_by_member_id`, `ix_member_classes_class_id`, `ix_member_paths_groups`,
`uq_members_email_lower`, `ix_seekers_member_id`, and **all six `ix_member_intents_*` partial
indexes** finished with `idx_scan = 0`. `ix_members_search_text_trgm` (5,488 kB, larger than the
2,176 kB `members` heap) had 3 scans. `members` alone: `seq_scan = 9,231`,
`seq_tup_read = 3,823,331`.

## 1.4 Verified fixes: the same queries after `CREATE INDEX CONCURRENTLY`

I created the candidate indexes on the scratch database, re-ran `ANALYZE`, and re-measured.

| Query | Before (buffers / ms) | After (buffers / ms) | Plan change |
| --- | --- | --- | --- |
| jobs.list default page | 230 / 87.5 | **3 / 0.065** | Seq Scan + top-N sort -> `Index Scan using ix_jobs_published_created` |
| housing.list page | 56 / 2.8 | **4 / 0.44** | Seq Scan + sort -> `Index Scan using ix_housing_listings_created_at` |
| announcements.list page | 148 / 32.7 | **65 / 16.2** | Seq Scan + sort -> `Index Scan using ix_announcements_board_order`; `is_read` subplan -> `Bitmap Index Scan using ix_announcement_reads_member_id` |
| one_member_per_company x8 | 22,337 / 616 | **1,596 / 155** | per-name Index Scan on name -> `BitmapOr(ix_members_current_company_trgm, ix_members_search_text_trgm)` |
| `saved_members WHERE saved_member_id` | 47 / 83.7 | **3 / 0.58** | Seq Scan -> `Index Only Scan` |
| `event_rsvps WHERE member_id` | 73 / 78.6 | **3 / 1.0** | Seq Scan -> `Index Only Scan` |
| `EXISTS positions.company ILIKE` | 459 / 45.5 | **102 / 37.6** | Seq Scan on positions -> `Bitmap Index Scan using ix_positions_company_trgm` |
| `EXISTS member_paths.current_group` | 35 / 1.2 | 35 / 0.32 - 8.1 | Seq Scan -> `Bitmap Index Scan using ix_member_paths_current_group` (1 buffer on the index side vs 25) |

**Honest negatives.** A GIN index on `members.skills` and a trigram index on `members.location`
were created and the planner **still chose a seq scan** for `skills && ARRAY[...]` and
`location ILIKE '%Munich%'` at 1,115 rows. Those two are not worth adding today.

---

# 2. Findings

Severity is about this system at its current and near-term size, not in the abstract.

| # | Sev | Rule id | Location (file:line) | Evidence | Impact (measured) | Recommended fix |
| --- | --- | --- | --- | --- | --- | --- |
| F-1 | **Critical** | `data-n-plus-one`, `query-covering-indexes` | `backend/members/infrastructure/orm_models.py:88-111` (six `lazy="selectin"` relationships); consumed at `_mappers.py:32-55` | Every `select(MemberRow)` fires six extra batch SELECTs. Probe: `search()` = **9 round trips**, `get_by_slug()` = 8, `get_many(40)` = 8. `to_member` reads only `classes`, `entry`, `intents`; `positions` (10,108 rows), `educations` (5,113) and `ca_details` are fetched and discarded on every directory page: 202 position rows incl. `description` text per 20-member page | 3 wasted round trips per list call. On a local socket that is ~2 ms; against Supabase (managed host, TLS, pooler hop) it is 3 x RTT per page, and it is the single largest structural cost in the read path | Change the three unused relationships to `lazy="raiseload"` (or `"select"`) on `MemberRow` and add explicit `.options(selectinload(...))` in `SqlMemberRepository.get_by_slug`/`get_by_id`, which are the only callers that need positions/educations/ca_detail. No migration; ORM-only change |
| F-2 | **High** | `data-pagination` | `members_repository.py:55-60`; `housing_repository.py:100-106`; `job_repository.py:103-107`; `_query.py:9-11`; `announcements_repository.py:68-78`; `member_cards.py:54-67`; `account_repository.py:44-51`; `events_repository.py:72-77` | Every list runs `SELECT count(*) FROM (<the filtered query>)` and then the page, so the predicate is evaluated twice | Directory page with `q=product`: **1,972 + 1,957 = 3,929 shared buffers, 2 round trips**. With `count(*) OVER ()`: **1,949 buffers, 1 round trip**. Exactly halves the work on every list endpoint | Replace the second statement with a window count in the page query: `select(MemberRow, func.count().over().label("total"))`. The repo already knows this trick, `members_repository.py:145` uses `count(*) OVER ()`. Keep `{items,total}` unchanged |
| F-3 | **High** | `query-missing-indexes`, `query-partial-indexes` | Index at `infrastructure/alembic/versions/001_initial_schema.py:908-914` vs sort at `backend/jobboard/infrastructure/job_repository.py:30-38` | `ix_jobs_published_list` is `(published_at DESC) WHERE status='published'`; the board's default `_order_by` returns `[JobRow.created_at.desc()]`. `docs/database-design.md:530` asserts the index "matches the board's default listing query exactly" | 6,000 synthetic jobs: **Seq Scan, 230 buffers, 87.5 ms**, top-N sort over 5,083 rows. Same query on `published_at DESC`: **Index Scan, 3 buffers, 0.031 ms** | `CREATE INDEX CONCURRENTLY ix_jobs_published_created ON jobs (created_at DESC) WHERE status = 'published';` (verified: 3 buffers / 0.065 ms). Or change `_order_by` to `published_at DESC` and delete the ambiguity |
| F-4 | **High** | `schema-foreign-key-indexes` | `001_initial_schema.py`: `saved_members` (no index on `saved_member_id`), `announcement_reads` / `event_rsvps` (composite PK leads with the parent id, none on `member_id`), `announcements.author_member_id`, `events.created_by_member_id`, `companies.created_by_member_id` | Skill detection query returns **6 unindexed FK columns**. Twelve tables cascade from `members`, and the loader rewrites the roster | `saved_members WHERE saved_member_id = ?`: **Seq Scan, 47 buffers, 83.7 ms**. `event_rsvps WHERE member_id = ?`: **73 buffers, 78.6 ms**. `announcement_reads WHERE member_id = ?`: **80 buffers**. After indexing: **3 / 3 / index-only**, 0.58 - 1.0 ms | Six `CREATE INDEX CONCURRENTLY` (SQL in section 3). `announcement_reads(member_id)` also fixes F-6 |
| F-5 | **High** | `query-missing-indexes`, `query-index-types` | `members_repository.py:141-158` (`one_member_per_company`), same predicate at `_member_query.py:99-105` | `current_company ILIKE :p OR search_text ILIKE lower(:p)`. `search_text` has a trigram GIN; `current_company` has **nothing**, so the whole `OR` degrades to a per-name full scan inside the LATERAL | **616 ms, 22,337 shared buffers** for 8 company names. `Rows Removed by Filter: 1046` per loop, 8 loops. This is a page render | `CREATE INDEX CONCURRENTLY ix_members_current_company_trgm ON members USING gin (current_company gin_trgm_ops);` Verified: **1,596 buffers, 155 ms** (14x fewer buffers, 4x faster) with `BitmapOr` over both trigram indexes |
| F-6 | **High** | `query-missing-indexes`, `query-composite-indexes` | `announcements_repository.py:27-36` (`is_read`), `:72-75` (sort); index at `001_initial_schema.py:611-616` | Sort is `is_pinned DESC, coalesce(published_at, created_at) DESC`; `ix_announcements_published_at` is `(published_at DESC)` and matches neither key. `is_read` is a correlated `EXISTS` on `announcement_reads(member_id)`, unindexed | Page: **148 buffers, 32.7 ms**, of which the `announcement_reads` seq scan is **26.9 - 31.5 ms** with `Rows Removed by Filter: 9588` | Expression index on the exact sort + the FK index from F-4. Verified together: **65 buffers, 16.2 ms** |
| F-7 | **Medium** | `query-missing-indexes`, `query-composite-indexes` | `housing_repository.py:33` vs index at `001_initial_schema.py:703-705` | `city.ilike(ilike_contains(f.city))` produces `city ILIKE '%Munich%'`, which a btree on `(city, status)` cannot serve. `idx_scan = 0` for `ix_housing_listings_city_status` after the full workload. There is no index for `ORDER BY created_at DESC` either | 2,000 synthetic listings: **Seq Scan, 56 buffers**, `Rows Removed by Filter: 1356`. After `ix_housing_listings_created_at`: **4 buffers, 0.44 ms** | Add `ix_housing_listings_created_at (created_at DESC)`. Then either make the city filter an equality (cities are a short closed set on this board) and keep the composite index, or add a trigram GIN on `city` and drop the dead composite |
| F-8 | **Medium** | `data-pagination` | `backend/core/api/pagination.py:15-19`; every `.offset(skip)` call site | Pure OFFSET/LIMIT everywhere, `limit <= 100` | Directory page 51 (`OFFSET 1000`) on the real 1,115-member table: **272 buffers, 2,249 kB quicksort, 4.9 - 36.5 ms**. Keyset on `(name, id)`: **39 buffers, 1.18 ms**. At 10x the roster this is a 2,000-row sort per page view | Keep OFFSET on the small boards. For the **directory** (the only list with a real deep-page path and a stable `name` sort), add an optional `after` cursor: `WHERE (name, id) > (:name, :id) ORDER BY name, id LIMIT :n`. `total` still comes from the window count of F-2. The `q`-sort branch (`_order_by`, `members_repository.py:39-40`) is not keyset-able as written; keyset only applies to `sort=name`/default-no-`q` |
| F-9 | **Medium** | `data-n-plus-one`, `monitor-explain-analyze` | `backend/paths/infrastructure/paths_repository.py:65-103` | `flow()` issues **7 statements**: 1 count, 3 single-column `GROUP BY`, 2 two-column `GROUP BY`, and one that ships **every** `member_paths` row joined to `member_intents` into Python (`:123`) | **7 round trips, 149.8 ms**, six full scans of the same 1,115-row table per request. The data changes only when the loader runs (`docs/database-design.md` section 9) | Two options, both good. (a) Collapse [1]-[6] into one `GROUP BY GROUPING SETS ((study_group),(first_step_group),(current_group),(study_group,first_step_group),(first_step_group,current_group),())` - one scan, one round trip. (b) Since the answer only changes on reload, make it a materialised view refreshed at the end of `PathService.recompute_all`, or cache the unfiltered flow in-process. Note the `filters` path (Ask narrows by `member_ids`) still needs the live query |
| F-10 | **Medium** | `query-missing-indexes` | `_member_query.py:145-150`, `_path_group_exists`; index at `001_initial_schema.py:254-259` | `ix_member_paths_groups (study_group, first_step_group, current_group)` only has a usable leftmost prefix for `study_group`. `?first_step_group=` and `?current_group=` filters, and `paths.member_ids_in(stage="current")` (`paths_repository.py:188-202`), get nothing | Seq Scan on `member_paths`, 25 buffers today. `idx_scan = 0` on the composite after the whole workload, so it is currently pure write overhead | `CREATE INDEX CONCURRENTLY ix_member_paths_current_group ON member_paths (current_group);` and the same for `first_step_group` (verified: index side drops 25 buffers -> 1). Then consider dropping `ix_member_paths_groups`, which nothing uses |
| F-11 | **Medium** | `conn-pooling`, `conn-prepared-statements` | `.env` `DATABASE_URL` / `DATABASE_MIGRATOR_URL`; `backend/core/settings/database.py:39,54-55`; `infrastructure/db.py:71-72` | `DATABASE_MIGRATOR_URL=` is empty, so `migrator_url_override or self.url` falls back to the runtime URL. Verified: `migrator_url` resolves to `postgresql+psycopg://...@aws-1-eu-north-1.pooler.supabase.com:5432/postgres`. ADR 0003 and `docs/database-design.md` section 11 both say Alembic must use a direct connection | Alembic runs DDL through Supavisor. Port 5432 on `pooler.supabase.com` is session mode so it will usually work, but it violates the documented rule and one pooler blip mid-migration leaves a half-applied revision | Set `DATABASE_MIGRATOR_URL` to the direct host (`db.<ref>.supabase.co:5432`), and make the empty string an error rather than a silent fallback: `migrator_url_override: str \| None` with a validator that maps `""` to `None` is fine, but log which URL Alembic resolved at startup |
| F-12 | **Medium** | `conn-prepared-statements` | `infrastructure/db.py:71-72, 85-88` | `_is_pooler_url` matches on `":6543/" or "pooler.supabase.com"`. The configured URL is `pooler.supabase.com:5432`, which is Supavisor **session** mode, where named prepared statements are safe. Verified `_is_pooler_url(async_url) -> True` | `statement_cache_size=0` and `prepared_statement_cache_size=0` are applied on a connection that does not need them: every statement is re-parsed and re-planned on every execution. The directory page's planning time was measured at **13 - 23 ms** on some plans, which is now paid per request | Detect the *mode*, not the host: disable the cache only when the port is 6543 (or an explicit `DATABASE_POOLER_MODE=transaction`). Keep the host check as a fallback but make the port the primary signal. Comment already explains the reason correctly at `db.py:86` |
| F-13 | **Medium** | `conn-prepared-statements`, `lock-short-transactions` | `infrastructure/db.py:79-84` | `statement_timeout` and `application_name` are passed as asyncpg `server_settings`, i.e. **startup parameters**. Verified working on a direct connection: `show statement_timeout -> 15s`, `show application_name -> cdtm-community-api` | Under PgBouncer transaction mode, startup parameters are only forwarded for keys in the pooler's tracked-parameter list; `application_name` is tracked by default, `statement_timeout` generally is **not**. If the deployment ever moves to port 6543, the 15 s guard may silently stop applying and the docs' promise at `docs/database-design.md:749-751` becomes false | Belt and braces: keep `server_settings`, and additionally issue `SET LOCAL statement_timeout = '15s'` at the start of each request's transaction (a `get_db` wrapper). `SET LOCAL` is transaction-scoped and safe under transaction pooling. Then verify with `show statement_timeout` against 6543 before switching |
| F-14 | **Low** | `conn-limits` | `backend/core/settings/database.py:40-41`; `infrastructure/db.py:92-95` | `pool_size=5`, `max_overflow=5` -> at most 10 server connections per process. `pool_pre_ping=True`, `pool_recycle=1800`, `application_name` all set correctly | Sane for one uvicorn process. The risk is arithmetic: N replicas x (5+5) plus Alembic plus `load_community.py` must stay under Supavisor's per-project pool and the instance `max_connections` (roughly 60 on the smallest Supabase compute, scaling with tier). Nothing in the repo asserts this | Document the budget next to the setting, and add a startup log line reporting `pool_size + max_overflow` and the resolved host. Confirm the project's actual pooler `default_pool_size` in the Supabase dashboard before scaling replicas past 4 |
| F-15 | **Low** | `schema-primary-keys` | `infrastructure/db.py:57-60` (`uuid_pk()` -> `gen_random_uuid()`), applied to `members`, `positions`, `educations`, `jobs`, `companies`, `seekers`, `events`, `announcements`, `intro_requests`, `housing_listings`, `accounts` | UUIDv4 primary keys: random insertion order, so every insert dirties a random btree leaf. The skill's `schema-primary-keys` calls this out explicitly | Real, but small here. `positions` is the highest-churn table (10,108 rows fully deleted and reinserted per load, `members_repository.py:278-299`); `pk_positions` is 424 kB and finished the audit with `idx_scan = 0`. At these volumes the bloat is not measurable | No change now. If `positions`/`jobs` reach millions of rows, move to `uuidv7()` (Postgres 18 has it natively; Supabase also ships `pg_uuidv7`) by changing the `server_default` only. Record the trade in an ADR rather than migrating today |
| F-16 | **Low** | `query-index-types` | `_member_query.py:93-96` (`roles.any` / `roles.overlap`), `:155-158` (`skills.overlap`, `languages.overlap`); array columns declared at `orm_models.py:68,78-79` | `'ca' = ANY (roles)` and `skills && ARRAY[...]` have no GIN index | Measured: **272 buffers / 2.2 ms** and **410 buffers / 4.0 ms** at 1,115 rows. **I created `ix_members_roles_gin` and `ix_members_skills_gin` and the planner still chose the seq scan** | Do **not** add these yet. The GIN indexes are dead weight at this size (`ix_members_search_text_trgm` is already 5,488 kB against a 2,176 kB heap). Revisit if `members` passes ~20k rows |
| F-17 | **Low** | `query-index-types`, `advanced-full-text-search` | `_member_query.py:106-144` (past_company, title, school, degree ILIKE inside EXISTS) | Free-text `ILIKE '%x%'` against `positions.company/title` (10,108 rows) and `educations.school/degree` (5,113) with no trigram index. The comment at `_member_query.py:60-63` claims "single-digit milliseconds" | Measured **45.5 ms / 459 buffers** for `past_company=McKinsey` and 10.0 ms for `school`. Not single-digit. After `ix_positions_company_trgm`: **37.6 ms / 102 buffers** | Add the two `positions` trigram indexes (company, title) when `positions` grows; `educations` can wait. Update the comment at `_member_query.py:60-63` with the measured numbers either way |
| F-18 | **Low** | `query-partial-indexes` | `001_initial_schema.py:384-425`; `orm_models.py:250-260` | Six partial boolean indexes on `member_intents`. All six finished the workload with `idx_scan = 0`. The predicate they would serve (`_member_query.py:159-170`) is an `EXISTS` over a **420-row** table that the planner reaches by seq scan (4 buffers) | Harmless (16 kB each) but they are not doing anything, and `docs/database-design.md:293-297` says only three exist, which is stale | Leave them; correct the doc to say six. Revisit only if `member_intents` approaches the size of `members` |
| F-19 | **Low** | `advanced-jsonb-indexing` | `orm_models.py:80` (`company_info: JSONB`) | No GIN index on `members.company_info` | Correct as-is: I found no query anywhere in `backend/` that filters on `company_info`. It is read whole by `_mappers.py:72` | None. Noted so a future `@>` filter does not land without an index |
| F-20 | **Nit** | `monitor-pg-stat-statements` | n/a | `select * from pg_extension` -> only `pg_trgm` and `plpgsql`. No `pg_stat_statements` | No production query-shape visibility. When a directory query gets slow on Supabase there is nothing to look at | `create extension if not exists pg_stat_statements;` (Supabase supports it; enable via the dashboard's extension list). Add it to the migration or the runbook |
| F-21 | **Nit** | `monitor-explain-analyze` | `docs/database-design.md:705-708` | The doc says "There is no functional index on `lower(email)`; the plain UNIQUE index is not usable by that predicate." | Wrong. `uq_members_email_lower` exists (`001_initial_schema.py:117`, `orm_models.py:115`) and `SqlMemberDirectory.find_member_id_by_email` (`backend/identity/infrastructure/member_directory.py:26`) is served by it | Correct the doc |
| F-22 | **Nit** | `data-batch-inserts` | `scripts/platform/load_community.py`; `members_repository.py:225-331` | `upsert_member` is one `commit()` per member and calls `self._s.refresh(row)` at `:326`, which triggers all six `selectin` loads for that member. Observed: 1,115 sequential upserts | The loader runs offline, so this is not a request-path cost; it is why a full load is minutes rather than seconds | Optional. If the load ever becomes painful, batch the `positions`/`educations` inserts with `executemany` and commit every N members. See the user's own note on binary `COPY` in FK order |

## Security note (question 7): RLS is done correctly

`infrastructure/alembic/versions/001_initial_schema.py:1047-1075`, `_lock_down_data_api()`:

1. `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY` for **all 21 tables** (iterating `DROP_ORDER`).
2. A guarded `DO $$ ... $$` that, **only if the `anon`/`authenticated` roles exist**, revokes
   `ALL` on all tables and sequences in `public` from both and sets `ALTER DEFAULT PRIVILEGES ...
   REVOKE ALL ON TABLES`.

Verified on the migrated database: `relrowsecurity = t` on all 21 application tables,
`relforcerowsecurity = f`. No policies exist, so `anon` and `authenticated` are **deny by default**
(`security-rls-basics`), and the grants are revoked on top (`security-privileges`). The API's
owner role bypasses RLS, which is what ADR 0003 intends. `relforcerowsecurity = f` is correct
here, not an oversight: forcing RLS on the owner with no policies would lock the API out of its
own tables.

**This is right and it is defence in depth done properly.** One thing to confirm out-of-band: the
migration only revokes if those roles are visible **at migration time**, so anyone restoring this
schema into a Supabase project must re-run the revoke if the roles were created afterwards. RLS
being enabled is the load-bearing half and it is unconditional.

---

# 3. Concrete DDL and the Alembic shape

Naming follows the repo's convention (`infrastructure/db.py:36-42`: `ix_%(column_0_label)s`, which
for SQLAlchemy-declared single-column indexes yields `ix_<table>_<column>`) and the hand-named
style already used for partial and composite indexes (`ix_jobs_published_list`,
`ix_housing_listings_city_status`, `ix_intro_requests_target`).

### Tier 1: add now (all measured above)

```sql
-- F-4: the six unindexed foreign keys (cascade + join)
CREATE INDEX CONCURRENTLY ix_announcement_reads_member_id
    ON announcement_reads (member_id);
CREATE INDEX CONCURRENTLY ix_event_rsvps_member_id
    ON event_rsvps (member_id);
CREATE INDEX CONCURRENTLY ix_saved_members_saved_member_id
    ON saved_members (saved_member_id);
CREATE INDEX CONCURRENTLY ix_announcements_author_member_id
    ON announcements (author_member_id);
CREATE INDEX CONCURRENTLY ix_events_created_by_member_id
    ON events (created_by_member_id);
CREATE INDEX CONCURRENTLY ix_companies_created_by_member_id
    ON companies (created_by_member_id);

-- F-3: the job board's actual default sort
CREATE INDEX CONCURRENTLY ix_jobs_published_created
    ON jobs (created_at DESC) WHERE status = 'published';
-- expected: Seq Scan + top-N sort (230 buffers) -> Index Scan (3 buffers)

-- F-6: the announcements board's actual sort
CREATE INDEX CONCURRENTLY ix_announcements_board_order
    ON announcements (is_pinned DESC, coalesce(published_at, created_at) DESC);
-- expected: Seq Scan + sort (148 buffers) -> Index Scan (65 buffers, with the FK index above)

-- F-5: "who works at X" (this one is worth the whole exercise)
CREATE INDEX CONCURRENTLY ix_members_current_company_trgm
    ON members USING gin (current_company gin_trgm_ops);
-- expected: 8x full scan (22,337 buffers) -> BitmapOr over two trigram indexes (1,596 buffers)

-- F-7: housing list ordering
CREATE INDEX CONCURRENTLY ix_housing_listings_created_at
    ON housing_listings (created_at DESC);
-- expected: Seq Scan + sort (56 buffers) -> Index Scan (4 buffers)

-- F-10: the two path-group columns the composite index cannot reach
CREATE INDEX CONCURRENTLY ix_member_paths_current_group
    ON member_paths (current_group);
CREATE INDEX CONCURRENTLY ix_member_paths_first_step_group
    ON member_paths (first_step_group);
-- expected: Seq Scan on member_paths (25 buffers) -> Bitmap Index Scan (1 buffer)
```

### Tier 2: add when the tables grow (do not add today)

```sql
-- F-17, when positions passes ~50k rows
CREATE INDEX CONCURRENTLY ix_positions_company_trgm
    ON positions USING gin (company gin_trgm_ops);   -- measured 459 -> 102 buffers today
CREATE INDEX CONCURRENTLY ix_positions_title_trgm
    ON positions USING gin (title gin_trgm_ops);
-- F-16, when members passes ~20k rows (planner ignores these at 1,115)
CREATE INDEX CONCURRENTLY ix_members_skills_gin ON members USING gin (skills);
CREATE INDEX CONCURRENTLY ix_members_roles_gin  ON members USING gin (roles);
-- admin-only "rows the matcher was unsure about"
CREATE INDEX CONCURRENTLY ix_members_needs_review
    ON members (name) WHERE needs_review;
```

### Candidates to drop (all `idx_scan = 0` after the full workload)

```sql
DROP INDEX CONCURRENTLY ix_member_paths_groups;          -- superseded by the two above
DROP INDEX CONCURRENTLY ix_housing_listings_city_status; -- unusable while city is ILIKE '%x%'
```

Confirm against `pg_stat_user_indexes` on the real Supabase database before dropping either;
my zero counts are from one synthetic workload, not from production traffic.

### Alembic migration shape

`CREATE INDEX CONCURRENTLY` cannot run inside a transaction, and Alembic wraps each revision in
one. Write the revision so it takes itself out of the transaction, and make the operations
idempotent so a failed run can be retried (`schema-constraints`, and PostgreSQL does support
`IF NOT EXISTS` for indexes):

```python
"""Indexes for the FK cascades and the real list sort orders.

Revision ID: 002_hot_path_indexes
Revises: 001_initial_schema
"""

from __future__ import annotations

from alembic import op

revision = "002_hot_path_indexes"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None

# CREATE INDEX CONCURRENTLY cannot run inside a transaction block, and this migration is
# expected to run against a database that is serving traffic. autocommit_block() commits the
# surrounding transaction and reopens one afterwards.
_CREATE = (
    ("ix_announcement_reads_member_id", "announcement_reads (member_id)"),
    ("ix_event_rsvps_member_id", "event_rsvps (member_id)"),
    ("ix_saved_members_saved_member_id", "saved_members (saved_member_id)"),
    ("ix_announcements_author_member_id", "announcements (author_member_id)"),
    ("ix_events_created_by_member_id", "events (created_by_member_id)"),
    ("ix_companies_created_by_member_id", "companies (created_by_member_id)"),
    ("ix_jobs_published_created", "jobs (created_at DESC) WHERE status = 'published'"),
    (
        "ix_announcements_board_order",
        "announcements (is_pinned DESC, coalesce(published_at, created_at) DESC)",
    ),
    ("ix_housing_listings_created_at", "housing_listings (created_at DESC)"),
    ("ix_member_paths_current_group", "member_paths (current_group)"),
    ("ix_member_paths_first_step_group", "member_paths (first_step_group)"),
)

_CREATE_GIN = (
    ("ix_members_current_company_trgm", "members USING gin (current_company gin_trgm_ops)"),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, target in _CREATE + _CREATE_GIN:
            table = target.split()[0]
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {target}")
            del table


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _ in _CREATE + _CREATE_GIN:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
```

Two notes for whoever writes it:

- Expression and partial indexes (`ix_announcements_board_order`, `ix_jobs_published_created`)
  must be mirrored in the ORM `__table_args__` or `tests/integration/test_migrations.py` will
  go red on the next autogenerate diff. Spell them as
  `Index("ix_announcements_board_order", text("is_pinned DESC"), text("coalesce(published_at, created_at) DESC"))`
  and `Index("ix_jobs_published_created", text("created_at DESC"), postgresql_where=text("status = 'published'"))`.
- `CREATE INDEX CONCURRENTLY` can leave an `INVALID` index behind if it is interrupted. After the
  migration, check `select indexrelid::regclass from pg_index where not indisvalid;` and re-run.

---

# 4. What is already done well

These are verified, not assumed.

- **The trigram index is real and it works.** `ix_members_search_text_trgm` turns a selective
  directory search into a bitmap index scan: `search_text ILIKE '%mckinsey%'` -> **207 buffers,
  1.2 ms** for 83 of 1,115 rows. The denormalised `search_text` haystack
  (`_mappers.py:79-108`) and its rebuild on **both** the loader path and the entry-edit path is
  exactly the discipline that keeps it correct, and the deliberate exclusion of a hidden Entry
  from the haystack (`_mappers.py:90-94`) closes a real oracle.
- **RLS and the Data API lockdown are correct** (`001_initial_schema.py:1047-1075`): RLS enabled
  on all 21 tables, no policies, grants revoked from `anon`/`authenticated`. Verified in the
  database. This is the right answer for an owner-role API and the reasoning in the docstring is
  accurate.
- **No true N+1 anywhere.** Every id-set lookup is batched: `_claimed_ids` uses
  `member_id = any(:ids)` (`members_repository.py:73`), `network` cards use
  `id = any(:ids)` (`member_directory.py:20-27`), the classifier's `iter_all` uses **keyset**
  batching (`career_history.py:56-80`, `WHERE id > :after ORDER BY id LIMIT 200`) with three
  batched child loads. `one_member_per_company` deliberately collapses fifty per-company
  lookups into one LATERAL statement with a comment explaining why. The `selectin` loads (F-1)
  are wasteful but they are still batched, not per-row.
- **`ask_quota` is one statement with no read-modify-write race** (`backend/core/llm/quota.py:28-41`):
  `INSERT ... ON CONFLICT DO UPDATE ... RETURNING asked`, exactly the `data-upsert` pattern, with
  the window pinned by `date_trunc('minute', now())` and the reasoning written down.
- **Connection settings are almost entirely right.** `pool_pre_ping=True`, `pool_recycle=1800`,
  `application_name='cdtm-community-api'`, `statement_timeout` from settings, `expire_on_commit=False`,
  `autoflush=False`. Verified live: `show statement_timeout -> 15s`,
  `show application_name -> cdtm-community-api`. The pooler statement-cache handling exists and is
  correctly explained; it just over-triggers (F-12).
- **`run_db` error mapping is better than the docs claim** (`infrastructure/repository.py:78-96`):
  it separates `57014` (statement timeout -> 504), `40001`/`40P01` (lost race -> retryable 503),
  `42xxx`/`22xxx` (our bug -> 500) from generic operational failure, and it rolls the session back
  so a deliberately-caught error does not poison every later query in the request. That last
  detail is the kind of thing people learn the hard way.
- **Types and constraints follow `schema-data-types` throughout.** `timestamptz` everywhere with
  `server_default now()`; `numeric(18,2)` for salaries and `integer` euros for rent with a stated
  reason; `text` not `varchar(n)`; arrays `NOT NULL DEFAULT '{}'`; `TEXT + CHECK` instead of
  `ENUM` with the migration-cost argument written out; `salary_currency ~ '^[A-Za-z]{3}$'` checked
  in the database; `owner_member_id <> saved_member_id` and `requester <> target` as constraints
  rather than only service-level rules. All identifiers are lowercase snake_case
  (`schema-lowercase-identifiers`).
- **The constraint naming convention** (`infrastructure/db.py:36-42`) plus
  `tests/integration/test_migrations.py` running `compare_metadata` against a scratch database is
  the reason this audit could trust the migration as the source of truth at all.
- **`uq_members_email_lower`** is a functional unique index on `lower(email)`, which is exactly
  what `find_member_id_by_email` needs. The docs say otherwise; the code is right (F-21).
- **`ON DELETE` choices are deliberate and correct**: `CASCADE` for everything derived from a
  member, `SET NULL` for the five edges that must survive a roster reload. Each one is justified
  in `docs/database-design.md` section 3.
- **The bounded-context read seams cost the schema nothing**: string FKs, `text()` reads in
  identity/network, metadata-free `sqlalchemy.table()` handles in paths. No table is mapped twice,
  which is why autogenerate stays honest.

---

# 5. Reproducing this

```bash
# scratch database, real member data, synthetic board data
createdb cdtm_perf_audit
DATABASE_URL=postgresql://localhost:5432/cdtm_perf_audit \
DATABASE_MIGRATOR_URL=postgresql://localhost:5432/cdtm_perf_audit \
  PYTHONPATH=. uv run alembic -c infrastructure/alembic.ini upgrade head
DATABASE_URL=postgresql://localhost:5432/cdtm_perf_audit \
  uv run python scripts/platform/load_community.py \
    --index frontend/public/data/index.json --profiles frontend/public/profiles
psql -d cdtm_perf_audit -f <scratchpad>/seed.sql      # synthetic board rows
psql -d cdtm_perf_audit -c 'vacuum analyze'
uv run python <scratchpad>/probe.py                    # exact SQL + round-trip counts
psql -d cdtm_perf_audit -f <scratchpad>/ex1.sql        # EXPLAIN (ANALYZE, BUFFERS)
```

Scratchpad artefacts: `probe.py`, `probe.out`, `seed.sql`, `ex1.sql`, `ex2.sql`, `load.log`.
Drop the scratch database with `dropdb cdtm_perf_audit` when done. No file in the repository was
created, modified or deleted.
