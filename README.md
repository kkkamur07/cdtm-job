# CDTM Community

The central place to connect the CDTM community more effectively.

It should help people discover each other quickly, start collaborations, and turn shared
interests into action, whether that is founding, mentoring, hiring, speaking, or hobbies. The
goal is clear value, low friction, and a reason to come back.

Concretely, that means one place where a Member can:

- find people by class, major, company, location, skill or what they are open to;
- say what they are open to: co-founding, mentoring, hiring, roles, speaking, investing;
- see where the community went, meaning what people studied, their first step after CDTM, and
  where they are now;
- act on it: save someone, ask for an intro, RSVP to an event, offer a room, post a job.

Everyone who has ever been through CDTM is in the directory, whether or not they ever sign in.
Sign-in is a CDTM Google Workspace account, one click, no password.

## Repository layout

One backend, one frontend, one database.

```text
backend/            FastAPI application
  core/             app factory, settings, error envelope, pagination, health
  identity/         Supabase Auth JWTs, Accounts, the Principal dependency
  members/          the directory: members, classes, entries, intents, the members Ask
  network/          saved members, intro requests
  paths/            where a class went afterwards, as a recomputed read model
  events/           events and RSVPs
  announcements/    announcements and read receipts
  housing/          housing listings and the housing Ask
  jobboard/         companies, jobs, seekers (ported from the standalone job board)
  media/            image uploads and reads, behind private buckets
infrastructure/     SQLAlchemy engines, declarative Base, Alembic migrations, run_db
scripts/platform/   export_openapi, load_community, match_workspace_emails, seed_dev_data
tests/              unit (no database) and integration (live local Postgres)
frontend/           Next.js 16 app, plus scripts/ingest.mjs (the LinkedIn + roster matcher)
data/               roster CSVs, Workspace export, raw scrape; never committed
docs/               architecture, database design, ADRs
```

Each of those is a bounded context with the same four layers (`api/`, `application/`,
`domain/`, `infrastructure/`) and a `CONTEXT.md` that defines its words. The two applications
this platform replaced are gone from the repository: the old job board became
`backend/jobboard/` plus the job pages in `frontend/`, and the old Community Tool became
`frontend/`. See [`CONTEXT-MAP.md`](CONTEXT-MAP.md) for how the contexts are allowed to know
about each other.

## Stack

| Layer | Choice |
| --- | --- |
| API | FastAPI, Python 3.11+, pydantic 2 |
| Persistence | SQLAlchemy 2 async over asyncpg, Alembic for schema |
| Database | Supabase Postgres (direct connection, not PostgREST) |
| Auth | Supabase Auth, Google Workspace `cdtm.com` |
| Storage | Supabase Storage (avatars) |
| Frontend | Next.js 16, React 19, Tailwind 4, `@supabase/supabase-js` for the session, `openapi-fetch` against a generated client |
| Ingest | Node, `sharp`, run locally against data that is never committed |
| Tooling | uv, poethepoet, ruff, pytest |

Why each of these, and what was rejected, is in [`docs/adr/`](docs/adr/README.md).

## Quick start: backend

Needs Python 3.11 or 3.12, [uv](https://docs.astral.sh/uv/), and a local Postgres 13+. Local
development needs no Supabase project.

```bash
uv sync

cp .env.example .env
createdb cdtm_community

uv run poe api          # alembic upgrade head, then uvicorn on :8000
```

| URL | |
| --- | --- |
| `http://localhost:8000/health` | status plus a database probe |
| `http://localhost:8000/docs` | Swagger UI (development and test only) |
| `http://localhost:8000/api/v1/...` | the API |

Optional, for something to look at:

```bash
uv run poe seed         # a few companies, jobs, an event, an announcement, a listing
```

## Quick start: frontend

```bash
cd frontend
npm install             # or bun install; sharp is needed by the ingest script
npm run dev             # http://localhost:3000
```

`frontend/.env.local` needs the API URL and the Supabase anon key:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

The API client is generated, never hand-written:

```bash
uv run poe openapi                      # backend -> frontend/openapi/openapi.json
cd frontend && npm run generate:api     # -> src/api/schema.d.ts
npm run check:api                       # fails if the committed schema is stale
```

Run both after any backend API change.

## Environment

The backend reads `.env` at the repository root (gitignored; the template is `.env.example`
next to it), then `backend/core/.env` if that exists too. Process environment always wins over
the files, and an empty value counts as unset.

| Variable | |
| --- | --- |
| `APP_ENVIRONMENT` | `development`, `test` or `production`. `production` turns off `/docs`. |
| `APP_CORS_ORIGINS` | comma-separated frontend origins |
| `DATABASE_URL` | runtime connection |
| `DATABASE_MIGRATOR_URL` | Alembic only; must be a **direct** connection. Defaults to `DATABASE_URL`. |
| `SUPABASE_URL` | project URL; used for JWKS and for Storage |
| `SUPABASE_JWT_SECRET` | legacy HS256 secret, if the project uses one |
| `SUPABASE_SERVICE_ROLE_KEY` | Storage only, server-side only, never in the frontend |
| `AUTH_ALLOWED_EMAIL_DOMAINS` | who may sign in; defaults to `cdtm.com` |
| `AUTH_ADMIN_EMAILS` | bootstrap admins, comma-separated |

## Supabase setup

1. Create a project. Note the project ref, the anon key, the service-role key and the database
   password.
2. In Auth, enable the Google provider, restrict it to the CDTM Workspace, and add the
   frontend origin and callback to the redirect allow-list. If the project still uses a legacy
   JWT secret, copy it to `SUPABASE_JWT_SECRET`; otherwise `SUPABASE_URL` alone is enough and
   the API verifies against the project's JWKS.
3. Under Database, copy both connection strings.
   - `DATABASE_MIGRATOR_URL`: the direct connection, port 5432. Alembic needs it.
   - `DATABASE_URL`: direct for a single long-lived API process; the transaction pooler
     (port 6543) for serverless or many replicas. The engine detects a pooler URL and disables
     prepared statements for it, which PgBouncer cannot support.
4. In Storage, create a public `avatars` bucket if you intend to serve avatars from Supabase
   rather than from `frontend/public/avatars/`.
5. Apply the schema: `uv run poe migrate`.

`pg_trgm` is created by the first migration; Supabase ships it.

## Commands

All from the repository root.

```bash
uv run poe migrate            # alembic upgrade head
uv run poe serve              # uvicorn --reload on :8000
uv run poe api                # migrate, then serve
uv run poe test-fast          # unit tests, no database
uv run poe test-integration   # integration tests, live local Postgres
uv run poe lint               # ruff check
uv run poe format             # ruff format
uv run poe format-check       # ruff format --check, rewrites nothing
uv run poe openapi            # export frontend/openapi/openapi.json
uv run poe openapi-check      # export, then fail if the committed schema is stale
uv run poe precommit          # lint, format-check, test-fast, openapi-check
uv run poe hooks-install      # install the git pre-commit hook, once per clone
uv run poe load-community     # load the ingest output into Postgres
uv run poe match-emails       # Workspace export -> data/derived/workspace-emails.csv
uv run poe seed               # development fixtures
```

`hooks-install` runs `git config core.hooksPath scripts/hooks`, and the tracked
`scripts/hooks/pre-commit` then runs `uv run poe precommit` before every commit. Integration
tests are not in it, because they need a live Postgres. `git commit --no-verify` skips it.

One test:

```bash
uv run pytest tests/integration/test_network.py -k intro -q
```

Frontend, from `frontend/`:

```bash
npm run dev
npm run build
npm run lint
npm run typecheck
npm run ingest                # node scripts/ingest.mjs
npm run generate:api
```

## Loading the community

Run by hand, in order. The inputs live in `data/` and never touch the server (ADR 0004);
[`data/README.md`](data/README.md) has the layout.

```bash
# 1. match LinkedIn scrapes against the roster CSVs; render avatars
cd frontend
node scripts/ingest.mjs
#    -> public/data/index.json, public/profiles/*.json, public/avatars/*.webp
#    -> src/generated/unmatched.json and review.csv for anything it was unsure about

# 2. load that into Postgres and compute career paths
cd ..
uv run poe load-community
```

The loader is idempotent (members keyed by slug, classes by their roster id), so re-running it
after a re-scrape updates in place.

Workspace e-mails arrive separately and are what binds logins to Members. `match-emails` reads
the Workspace export from `data/workspace/`, matches it to members by name, and writes
`data/derived/workspace-emails.csv`; the loader then binds the addresses:

```bash
uv run poe match-emails
uv run poe load-community --emails data/derived/workspace-emails.csv     # slug,email
```

## Testing

```bash
uv run poe test-fast          # tests/unit
uv run poe test-integration   # tests/integration
```

Integration tests are real: the actual app, an actual local Postgres, `alembic upgrade head`
once per session, and a `TRUNCATE` of every table between tests. A loopback guard refuses any
database host that is not `localhost`, `127.0.0.1` or `::1`, so an exported Supabase
`DATABASE_URL` cannot wipe a real database.

`tests/integration/test_migrations.py` migrates a scratch database from empty to head and
asserts Alembic's `compare_metadata` against the ORM is empty. Change a model without a
migration and it goes red.

How strong the tests are is measured with mutmut; the first whole-backend campaign took the
kill rate from 55% to 93% and its findings, the per-slice procedure and the tool's blind spots
are in [`docs/mutation-testing.md`](docs/mutation-testing.md).

## Data and privacy

This repository handles real people's data. `data/` holds the roster CSVs, the Google
Workspace export and the raw LinkedIn scrape, and nothing in it except `data/README.md` is
committed. `frontend/data/`, `*.xlsx`, `05_2026/` and `05_2026.zip` are legacy locations and
stay in `.gitignore`.

The API redacts a Member's e-mail from anyone who is not looking at their own profile, and an
Entry set to `hidden` is not shown to other Members.

## Documentation

| Doc | |
| --- | --- |
| [`docs/README.md`](docs/README.md) | index |
| [`docs/architecture.md`](docs/architecture.md) | contexts, request flow, auth, errors, deployment |
| [`docs/database-design.md`](docs/database-design.md) | every table, index, constraint, and the Supabase connection rules |
| [`docs/adr/`](docs/adr/README.md) | why it is like this |
| [`docs/mutation-testing.md`](docs/mutation-testing.md) | how strong the tests are, running mutmut, the first campaign's findings |
| [`backend/README.md`](backend/README.md) | routes, services, settings, tests |
| [`infrastructure/README.md`](infrastructure/README.md) | engines and migrations |
| [`CONTEXT-MAP.md`](CONTEXT-MAP.md) | the domain vocabulary of each context |
| [`TODO.md`](TODO.md) | internal backlog |
