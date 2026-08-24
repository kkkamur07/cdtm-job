# 0003. SQLAlchemy and Alembic straight against Supabase Postgres

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: how the API reaches the database, who owns the schema, and what
  Supabase is still used for. It does not cover the table design itself
  (see [`../database-design.md`](../database-design.md)).

## Context

The old job board reached Postgres through `supabase-py`, which is a client for PostgREST.
Every repository method was a chain of `.select().eq().limit()` calls wrapped in
`supabase_execute("ctx.op", lambda: ...)`, and the schema lived in hand-written SQL under
`infrastructure/supabase/supabase/migrations/`, applied with `supabase db push`.

That worked while the job board was three flat tables with no joins. The merged platform is
not that. A single directory search filters on the member row, a class membership, an intents
row, an entry row, a skills array and an `exists` against `accounts`, then pages the result
and returns a total. Career paths aggregate three columns into a flow graph. Announcements
carry a per-viewer unread flag.

PostgREST can express some of that with embedded resources and `rpc` functions, and none of it
readably. It also cannot express a transaction across two tables at all: the API had already
grown places where "upsert the member, then upsert its positions" was two HTTP round trips
with a window in between.

## Decision

The API connects to Postgres directly with SQLAlchemy 2 (async, asyncpg), and Alembic owns
the schema.

- `infrastructure/db.py` builds two engines from one `DATABASE_URL`: async `asyncpg` for the
  app, sync `psycopg` for Alembic and scripts.
- `infrastructure/models.py` imports every context's `orm_models` so `Base.metadata` is
  complete; it is the only thing Alembic's `env.py` imports.
- `infrastructure/repository.py::run_db` wraps every database call and maps driver errors onto
  `backend.core.exceptions`: `23505` to `ConflictError` (409), other integrity errors to
  `ValidationError` (422), operational errors to `RepositoryError` (503). It is the direct
  descendant of the job board's `supabase_execute`, and it exists for the same reason:
  application code must never catch a driver exception.
- Repositories never commit. The application service that owns the use case does, so a use
  case that touches several aggregates is one transaction.

Supabase stays, for the parts that are not the schema: Auth issues the Google Workspace
sign-in and the JWT (ADR 0001), Storage is the intended home for member avatars
(`StorageSettings`, `avatars` bucket), and Postgres brings managed hosting, backups and the
connection poolers.

Supabase's PostgREST is not used, and the browser never talks to Supabase's data APIs. The API
does not rely on RLS either: it connects as an owning role and enforces every access rule in
`application/` services. RLS may still be enabled as defence in depth for anything else that
reaches the database, but no application behaviour depends on it.

## Rationale

The queries the product needs are joins. Writing them in SQLAlchemy Core and having a
type-checked ORM row on the other side is cheaper to write, cheaper to read and cheaper to
change than the equivalent PostgREST embedding.

Migrations should be reviewable and testable. `tests/integration/test_migrations.py`
migrates a scratch database from empty to head and runs Alembic's `compare_metadata` against
`Base.metadata`. Add a column to an ORM model without a migration and the suite goes red.
There is no equivalent check when the schema is a folder of SQL files and the models are a
separate hand-maintained mirror.

Two authorization systems is one too many. Once the API enforces "only the target of an
intro request may accept it", encoding a weaker version of the same rule in RLS policies adds
a second place to be wrong without removing the first.

Alternatives considered:

- *Keep supabase-py, add `rpc` functions for the hard queries.* Rejected: it moves the
  application's logic into SQL functions that Alembic does not manage and tests cannot easily
  reach.
- *Supabase CLI migrations plus SQLAlchemy for reads.* Rejected: two owners of one schema is
  the failure mode `test_migrations.py` exists to prevent.
- *Let the browser talk to PostgREST with RLS.* Rejected: it makes RLS the entire security
  model for a directory of real people's contact details, and there is no place left to put
  "redact the e-mail unless you are looking at yourself" (`MemberService._redact`).

## Consequences

- The service-role key is no longer a request-path credential. It is only needed for Storage,
  server-side. `DATABASE_URL` is the credential that matters now, and it never reaches the
  browser.
- Supabase's pooler (PgBouncer, transaction mode, port 6543) cannot track prepared statements,
  so `get_async_engine` sets `statement_cache_size=0` when the URL looks like a pooler URL.
  Alembic must use a direct connection: `DATABASE_MIGRATOR_URL`.
- A statement timeout is set per connection (`DATABASE_STATEMENT_TIMEOUT_MS`, default 15 s) via
  asyncpg `server_settings`, so one bad directory query cannot pin a pooled connection.
- Local development no longer needs a Supabase project at all: a plain local Postgres and a
  `SUPABASE_JWT_SECRET` are enough, which is exactly what the integration suite uses.
- Tests are real: `tests/integration/` runs against a live local Postgres, truncating every
  table between tests behind a loopback-only guard.
