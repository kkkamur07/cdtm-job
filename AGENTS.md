# AGENTS.md

Guidance for coding agents (Claude Code, Cursor, Codex and the like) working in this
repository. There is no CLAUDE.md; this file is the one set of instructions.

## What this is

The CDTM Community platform: one FastAPI backend and one Next.js frontend over Supabase
Postgres. It is the member directory (everyone who has ever been through CDTM), what Members
maintain about themselves, the network features, events, announcements, housing, career paths,
and the job board that used to be a separate app.

Read [`docs/architecture.md`](docs/architecture.md) before making a structural change and
[`docs/adr/`](docs/adr/README.md) before proposing that something be otherwise.

## Repository layout

One `pyproject.toml`, one virtualenv, one Alembic history. Run every backend command from the
repository root.

```text
backend/            FastAPI application
  core/             app factory, settings, exceptions, error envelope, pagination, health
  identity/         Supabase Auth JWTs, Accounts, the Principal dependency
  members/          the directory: members, classes, entries, intents, and the members Ask
  network/          saved members, intro requests
  paths/            the derived career-path read model and the Sankey flow
  events/           events and RSVPs
  announcements/    announcements and read receipts
  housing/          housing listings and the housing Ask
  jobboard/         companies, jobs, seekers
  media/            image uploads and reads (storage port, local disk + Supabase adapters)
infrastructure/     SQLAlchemy engines, Base, Alembic, run_db          (root-level, shared)
scripts/platform/   export_openapi.py, load_community.py, match_workspace_emails.py,
                    seed_dev_data.py, _bootstrap.py
tests/unit/         no database
tests/integration/  live local Postgres
frontend/           Next.js 16 app; scripts/ingest.mjs is the LinkedIn + roster matcher
data/               roster CSVs, Workspace export, raw scrape; never committed
docs/               architecture.md, database-design.md, mutation-testing.md, adr/
```

## Commands

```bash
uv sync
uv run poe migrate            # alembic upgrade head
uv run poe serve              # uvicorn backend.core.main:app --reload --port 8000
uv run poe api                # migrate, then serve
uv run poe test-fast          # tests/unit (marker: not integration)
uv run poe test-integration   # tests/integration (marker: integration)
uv run poe lint               # ruff check backend infrastructure scripts tests
uv run poe format             # ruff format
uv run poe format-check       # ruff format --check, rewrites nothing
uv run poe openapi            # export frontend/openapi/openapi.json
uv run poe openapi-check      # export, then fail if the committed schema is stale
uv run poe precommit          # lint, format-check, test-fast, openapi-check
uv run poe hooks-install      # git config core.hooksPath scripts/hooks (run once per clone)
uv run poe load-community     # load the ingest output into Postgres
uv run poe match-emails       # Workspace export -> data/derived/workspace-emails.csv
uv run poe seed               # development fixtures
```

`hooks-install` is one command per clone: it points git at the tracked `scripts/hooks/`, so
`scripts/hooks/pre-commit` runs `uv run poe precommit` before every commit. `git commit
--no-verify` skips it. There is no `pre-commit` framework here and there is not going to be
one; the hook is the poe tasks.

Single test file, or a single test:

```bash
uv run pytest tests/integration/test_members.py -q
uv run pytest tests/integration/test_network.py -k intro -q
uv run pytest tests/unit/test_paths_classifier.py::test_classify_career_groups_titles_and_companies -q
```

Frontend, from `frontend/`:

```bash
npm install
npm run dev
npm run build
npm run lint
npm run typecheck
npm run ingest                # node scripts/ingest.mjs
npm run generate:api          # openapi/openapi.json -> src/api/schema.d.ts
npm run check:api             # fails if the committed schema is stale
```

Alembic directly (the `poe` tasks set `PYTHONPATH` for you; a bare invocation does not):

```bash
PYTHONPATH=. alembic -c infrastructure/alembic.ini current
PYTHONPATH=. alembic -c infrastructure/alembic.ini revision --autogenerate -m "describe change"
PYTHONPATH=. alembic -c infrastructure/alembic.ini downgrade -1
```

## Architecture map

Five bounded contexts, four layers each, dependency arrows in one direction only.

```text
backend/<context>/
  api/               FastAPI routers, request/response schemas, DI wiring
  application/       one <noun>_service.py per aggregate, commands.py, ports.py (Protocols)
  domain/            pydantic aggregates and StrEnums; imports no framework
  infrastructure/    orm_models.py, one <noun>_repository.py per aggregate
```

| Context | Owns | Depends on |
| --- | --- | --- |
| `core` | `create_app()`, settings, exceptions, pagination, health | nothing |
| `identity` | `accounts`, JWT verification, `Principal` | `core` |
| `members` | members, classes, entries, intents, the members Ask | `core`, `identity` (deps only) |
| `network` | saved members, intro requests | `core`, `identity` (deps only) |
| `paths` | `member_paths`, the classifier, the flow | `core`, `identity` (deps only) |
| `events` | events, RSVPs | `core`, `identity` (deps only) |
| `announcements` | announcements, read receipts | `core`, `identity` (deps only) |
| `housing` | housing listings, the housing Ask | `core`, `identity` (deps only) |
| `jobboard` | companies, jobs, seekers | `core`, `identity` (deps only) |
| `media` | image uploads and reads (private buckets behind the API) | `core`, `identity` (`PrincipalDep` only) |

Cross-context seams, and there are only four kinds:

- Every board imports `backend/identity/api/deps.py` for the auth dependencies.
- Board services take an `Actor` (`backend/core/actor.py`: member id, admin flag), never a
  `Principal`. `ActorDep`, `MemberActorDep` and `OptionalActorDep` in
  `backend/identity/api/deps.py` are the only translation point.
- A context that must read another context's tables does it through a read port and never an
  ORM import: `identity` and `network` use raw `text()` queries (`infrastructure/member_directory.py`
  in each), `paths` uses the metadata-free `sqlalchemy.table()` handles in
  `backend/paths/infrastructure/_member_tables.py` so Alembic never sees a second mapping, and
  `members` reads `accounts` the same way for `Member.is_claimed`.
- An `api/` module may compose two contexts into one response, and that is the only layer that
  may: `backend/members/api/ask.py` puts the Paths flow on a members Ask answer.

No two boards may import each other's `application/`, `domain/` or `infrastructure/`. Their
only intended coupling is FK columns (`jobs.posted_by_member_id`, `seekers.member_id`,
`events.created_by_member_id`, `announcements.author_member_id`, `housing_listings.member_id`),
which stay string references so the ORM classes never meet.

### Key files

| Concern | File |
| --- | --- |
| App factory, CORS, security headers, error handlers, router wiring | `backend/core/app.py` |
| Uvicorn entrypoint | `backend/core/main.py` |
| Exception hierarchy (the only errors application code raises) | `backend/core/exceptions.py` |
| Settings, one class per concern | `backend/core/settings/{app,database,auth,storage}.py` |
| Env template | `.env.example` (repository root) |
| Auth dependencies (`PrincipalDep` and friends) | `backend/identity/api/deps.py` |
| Token verification | `backend/identity/infrastructure/jwt_verifier.py` |
| Engines, Base, session, pooler handling | `infrastructure/db.py` |
| ORM aggregation for Alembic | `infrastructure/models.py` |
| Driver error mapping (`run_db`) | `infrastructure/repository.py` |
| Schema | `infrastructure/alembic/versions/001_initial_schema.py` |
| Search haystack, row-to-domain mapping | `backend/members/infrastructure/_mappers.py` |
| The WHERE clause behind `MemberFilters` | `backend/members/infrastructure/_member_query.py` |
| Career path classifier | `backend/paths/infrastructure/paths_classifier.py` |
| Members tables as paths sees them (no ORM import) | `backend/paths/infrastructure/_member_tables.py` |
| Ask quota, shared across processes | `backend/core/llm/quota.py`, table `ask_quota` |

## Conventions

- Python 3.11 or 3.12, `from __future__ import annotations` at the top of every module.
- ruff, line length 100, rules `F`, `I`, `UP`, `B`, `SIM`, `S`. `frontend` and the retired
  top-level app directories are excluded.
- Domain models are `extra="forbid"`, so a typo in a request body is a 422 rather than a
  silently ignored field.
- `XPublic` subclasses the domain model; `XsPublic` is `{items, total}`. These are the OpenAPI
  contract the frontend client is generated from.
- Lists take `skip` and `limit` (capped at 100 in `backend/core/api/pagination.py`) and return
  `{items, total}`.
- `PATCH` and `PUT` bodies use optional fields, so an unset field is left alone rather than
  nulled.
- Errors are `{"error": {"code", "message", "ref"}}` with the same `ref` in `X-Error-ID`.
  Below 500 the message is shown to the caller; write it for a person. At or above 500 it is
  replaced and logged with a stack trace.
- Repositories never commit. The service owning the use case does. Every database call goes
  through `run_db("context.operation", fn)`.
- Authorization lives in `application/`, never in a router. Routers pick a dependency
  (`PrincipalDep`, `MemberPrincipalDep`, `AdminPrincipalDep`) and pass an `Actor` down.
- Comments explain *why*, and name the concrete reason. "PgBouncer in transaction mode cannot
  track prepared statements" beats "disable statement cache".
- `domain/` imports no framework. No FastAPI, no SQLAlchemy.

### Adding a field or an endpoint

ORM model -> Alembic revision -> domain model -> `commands.py` -> repository -> router (and
`api/schemas.py` if the response shape changed) -> `uv run poe openapi` ->
`npm run generate:api` in `frontend/`.

Regenerate the OpenAPI client after any backend API change. `frontend/openapi/openapi.json`
and `frontend/src/api/schema.d.ts` are committed and never hand-edited.

A new bounded context with tables must be imported in `infrastructure/models.py`, or Alembic
will not see it.

## Data pipeline

Run by hand, in order. None of it runs on the server. The inputs live in `data/`, which
[`data/README.md`](data/README.md) lays out.

```bash
cd frontend && node scripts/ingest.mjs   # roster CSVs + LinkedIn scrape -> JSON + avatars
cd .. && uv run poe load-community       # JSON -> Postgres, plus career paths
```

`ingest.mjs` is the matcher: it joins scrapes to roster rows by name and writes
`public/data/index.json`, `public/profiles/*.json`, `public/avatars/*.webp`, plus
`src/generated/unmatched.json` and `review.csv` for anything it was unsure about. It reads
`../data/roster/*.csv` and `../data/linkedin/05_2026` by default; `--data`, `--people`,
`--classes`, `--students`, `--cas` and `--overrides` point it somewhere else.
`load_community.py` is a loader only; it makes no matching decisions and carries `matched`,
`match_method` and `needs_review` through as data (ADR 0004).

Workspace e-mails, which are what bind logins to Members, load separately. `match-emails`
matches the export in `data/workspace/` to members by name (exact, then the e-mail local part,
then fuzzy, with ambiguous rows written to a review file) and produces the CSV the loader
reads:

```bash
uv run poe match-emails
uv run poe load-community --emails data/derived/workspace-emails.csv     # slug,email
```

## Caveats

- PII must never be committed. `data/` holds the roster CSVs, the Google Workspace export and
  the raw LinkedIn scrape, and nothing in it except `data/README.md` is tracked.
  `frontend/data/`, `*.xlsx`, `05_2026/` and `05_2026.zip` are legacy locations kept in
  `.gitignore`. Do not add any of it, do not paste its contents into files, do not put real
  names or e-mails in fixtures or docs.
- The two applications this platform replaced are gone from the repository. The old job board
  became `backend/jobboard/` plus the job pages in `frontend/`, and the old Community Tool
  became `frontend/`. Neither directory exists any more; ADR 0002 records what they were.
- Integration tests wipe the database. They `TRUNCATE` every table between tests, behind a
  loopback-only guard. If `DATABASE_URL` points at anything but `localhost`, `127.0.0.1` or
  `::1`, the suite refuses to run. Never remove that guard.
- Alembic must use a direct Postgres connection. `DATABASE_MIGRATOR_URL` exists for this. DDL
  through Supabase's transaction pooler (port 6543) is a good way to lose a migration halfway.
- On the pooler, prepared statements are off. `infrastructure/db.py::_is_pooler_url` detects it
  and sets `statement_cache_size=0`. If you see
  `prepared statement "__asyncpg_stmt_N__" already exists`, that detection missed.
- `APP_ENVIRONMENT=production` disables `/docs`, `/redoc` and `/openapi.json`. Generate the
  client from the committed schema instead.
- An empty env value counts as unset (`env_ignore_empty=True`). `SUPABASE_JWT_SECRET=` means
  no secret, not an empty secret.
- `search_text` is denormalised and must be rebuilt whenever a Member's scrape or Entry
  changes. It is refreshed in `SqlMemberRepository.upsert_member` and `SqlEntryRepository.upsert`;
  a new write path that touches those fields needs the same call.
- Enumerations are `TEXT` with `CHECK`, never Postgres `ENUM`. Adding a value is a constraint
  swap in one transaction. Keep it that way.
- `accounts.auth_user_id` is deliberately not a foreign key. The `auth` schema belongs to
  Supabase and does not exist in a local Postgres.

## Domain language

Use the words the context uses. Do not say "user": Community says **Member**, Identity says
**Account**.

- [`CONTEXT-MAP.md`](CONTEXT-MAP.md): the three contexts and how they relate
- [`backend/members/CONTEXT.md`](backend/members/CONTEXT.md)
- [`backend/network/CONTEXT.md`](backend/network/CONTEXT.md)
- [`backend/paths/CONTEXT.md`](backend/paths/CONTEXT.md)
- [`backend/events/CONTEXT.md`](backend/events/CONTEXT.md)
- [`backend/announcements/CONTEXT.md`](backend/announcements/CONTEXT.md)
- [`backend/housing/CONTEXT.md`](backend/housing/CONTEXT.md)
- [`backend/identity/CONTEXT.md`](backend/identity/CONTEXT.md)
- [`backend/jobboard/CONTEXT.md`](backend/jobboard/CONTEXT.md)
