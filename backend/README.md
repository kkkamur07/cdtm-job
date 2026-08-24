# Backend

The FastAPI backend for the CDTM Community platform: the member directory, what Members
maintain about themselves, the network features, events, announcements, housing, career paths,
and the job board.

One application, five bounded contexts, one database. Run every command from the repository
root.

## Quick start

```bash
uv sync
cp .env.example .env                               # then set DATABASE_URL
createdb cdtm_community
uv run poe api                                    # migrate, then serve on :8000
```

| URL | |
| --- | --- |
| `http://localhost:8000/` | service banner |
| `http://localhost:8000/health` | status plus a database probe |
| `http://localhost:8000/docs` | Swagger UI (development and test only) |
| `http://localhost:8000/api/v1/...` | the API |

Nothing here needs a Supabase project. A local Postgres and a `SUPABASE_JWT_SECRET` are enough
to run and test everything, which is exactly what the integration suite does.

## Tasks

```bash
uv run poe migrate            # alembic upgrade head
uv run poe serve              # uvicorn backend.core.main:app --reload --port 8000
uv run poe api                # migrate, then serve
uv run poe test-fast          # unit tests, no database
uv run poe test-integration   # integration tests, live local Postgres
uv run poe lint               # ruff check
uv run poe format             # ruff format
uv run poe openapi            # export frontend/openapi/openapi.json
uv run poe load-community     # load ingest output into Postgres
uv run poe match-emails       # Workspace export -> data/derived/workspace-emails.csv
uv run poe seed               # development fixtures
```

One test, one file:

```bash
uv run pytest tests/integration/test_network.py -k intro -q
uv run pytest tests/unit/test_paths_classifier.py -q
```

## Directory map

```text
backend/
  core/                          cross-cutting; imports no other context
    app.py                       create_app(): CORS, security headers, error handlers, routers
    main.py                      uvicorn entrypoint (app = create_app())
    exceptions.py                AppError hierarchy: the only errors application code raises
    page.py                      PageResult[T], the application-layer page
    mapping.py                   dump_for_db(): pydantic -> DB-API types
    api/health.py, api/root.py, api/pagination.py
    schemas/errors.py            the {"error": {...}} envelope model
    schemas/page.py              Page[T] = {items, total}
    llm/                         StructuredCompleter port, OpenAI-compatible and Anthropic
                                 adapters, strict JSON schema, the ask_quota meter and its
                                 in-process fallback bucket (see docs/ask.md)
    actor.py                     Actor: the member id and admin flag a board is given
    settings/                    one settings class per concern (see below)

  identity/                      Account, JWT verification, the Principal dependency
    api/deps.py                  PrincipalDep and friends; every other context imports these
    api/router.py                /auth/me, /auth/accounts/{id}/bind, /auth/accounts/{id}/admin
    api/dev_router.py            /auth/dev/*, mounted only with AUTH_DEV_LOGIN_ENABLED
    application/auth_service.py  AuthService: verify, allow-list, upsert, bind
    application/dev_login_service.py  local sign-in, then the ordinary authenticate()
    application/ports.py         TokenVerifier, AccountRepository, MemberDirectory protocols
    domain/account.py            TokenClaims, Account, Principal
    domain/directory.py          MemberSummary, what identity knows about a Member
    infrastructure/              jwt_verifier.py, dev_token_issuer.py, orm_models.py,
                                 account_repository.py, member_directory.py

  members/                       the directory
    api/                         members.py, me.py, ask.py, schemas.py, deps.py
    application/                 member_service.py, entry_service.py, ask_service.py,
                                 import_service.py, commands.py, ports.py
    domain/                      member.py, entry.py, ask.py
    infrastructure/              orm_models.py, members_repository.py, entry_repository.py,
                                 _mappers.py, _member_query.py, ask_translator_{llm,rules}.py

  network/                       saved people and intro requests
    api/                         network.py, schemas.py, deps.py
    application/                 network_service.py, commands.py, ports.py
    domain/                      network.py
    infrastructure/              orm_models.py, network_repository.py, member_directory.py

  paths/                         where a class went afterwards (a derived read model)
    api/                         paths.py, schemas.py, deps.py
    application/                 path_service.py, ports.py
    domain/                      paths.py, card.py
    infrastructure/              orm_models.py, paths_repository.py, paths_classifier.py,
                                 career_history.py, member_cards.py, _member_tables.py

  events/                        events and RSVPs
  announcements/                 announcements and read receipts
    api/ application/ domain/ infrastructure/   same four layers as the rest

  housing/                       housing listings and the housing Ask
    api/                         housing.py, ask.py, schemas.py, deps.py
    application/                 housing_service.py, housing_ask_service.py, visibility.py
    domain/                      housing.py, ask.py
    infrastructure/              orm_models.py, housing_repository.py,
                                 housing_ask_translator_{llm,rules}.py

  jobboard/                      companies, jobs, seekers; the ported job board
    api/                         companies.py, jobs.py, seekers.py, ask.py, schemas.py, deps.py
    application/                 company_service.py, job_service.py, seeker_service.py,
                                 commands.py, ports.py
    domain/                      company.py, job.py, seeker.py
    infrastructure/              orm_models.py, _query.py, one <noun>_repository.py each

  media/                         image uploads and reads; private buckets behind the API
    api/router.py                POST /media/{kind}, GET /media/{bucket}/{key}, DELETE
    infrastructure/              ports.py (BlobStorage), images.py, local_disk.py,
                                 supabase_storage.py

infrastructure/                  shared: engines, Base, Alembic, run_db   (see its README)
scripts/platform/                export_openapi, load_community, seed_dev_data
tests/unit, tests/integration
```

## Architecture

Four layers per context, and the dependency arrows only point one way:

```text
backend/<context>/
  api/               FastAPI routers, request/response schemas, DI wiring
  application/       services (use cases, authorization), commands, ports (Protocols)
  domain/            pydantic aggregates and StrEnums; imports no framework
  infrastructure/    SQLAlchemy ORM models and repositories
```

The rules that keep it honest:

- `domain/` imports nothing from FastAPI or SQLAlchemy. It is pydantic and `StrEnum`, and it is
  what ends up in the OpenAPI document.
- `application/` owns authorization and transactions. A router never decides who may do what.
  Services raise `backend.core.exceptions`; nothing catches a driver error above
  `infrastructure/`.
- `ports.py` is a `Protocol`, not an ABC. Repositories satisfy it structurally, so unit tests
  can pass a hand-written fake without inheriting anything.
- Repositories never commit. The service that owns the use case does, so a use case touching
  several aggregates is one transaction.
- `core/app.py` is the only file that knows the app object exists. Contexts export an
  `APIRouter` and nothing else.
- ORM metadata is aggregated in `infrastructure/models.py` for Alembic. A new context with
  tables must be imported there.

### Adding a field or an endpoint

ORM model -> Alembic revision -> domain model -> `commands.py` -> repository -> router (and
`api/schemas.py` if the response shape changed) -> `uv run poe openapi` -> `npm run
generate:api` in `frontend/`.

## Contexts

| Context | Responsibilities | Key files |
| --- | --- | --- |
| `core` | App factory, per-concern settings, error envelope, pagination, health | `core/app.py`, `core/exceptions.py`, `core/settings/` |
| `identity` | Verify Supabase JWTs, allow-list the e-mail domain, upsert the Account, bind it to a Member, publish `Principal` | `identity/application/auth_service.py`, `identity/infrastructure/jwt_verifier.py`, `identity/api/deps.py` |
| `members` | Directory search and profiles, Entry and Intents, the Ask over the directory, the loader's import service | `members/application/member_service.py`, `members/infrastructure/members_repository.py`, `members/infrastructure/_member_query.py` |
| `network` | Saved people and intro requests: the edge between two members, never a copy of one | `network/application/network_service.py`, `network/infrastructure/member_directory.py` |
| `paths` | The `member_paths` read model, the classifier that fills it, the Sankey flow and the people in each box | `paths/application/path_service.py`, `paths/infrastructure/paths_classifier.py`, `paths/infrastructure/_member_tables.py` |
| `events` | Events and RSVPs | `events/application/event_service.py` |
| `announcements` | Announcements, read receipts and the unread count | `announcements/application/announcement_service.py` |
| `housing` | Listings, expiry and renewal, the view counter, the Ask over the board | `housing/application/housing_service.py`, `housing/application/visibility.py` |
| `jobboard` | Companies, jobs, seekers. Same `/api/v1` contract as the standalone job board | `jobboard/api/jobs.py`, `jobboard/application/job_service.py` |
| `media` | Image uploads and reads behind the API; private buckets, local disk or Supabase Storage | `media/api/router.py`, `media/infrastructure/ports.py` |

Contexts do not import each other's internals. The four deliberate seams:

- Every board imports `identity/api/deps.py` for the auth dependencies.
- No board ever sees a `Principal`. Their services take an `Actor` (`core/actor.py`: member id,
  admin flag); `ActorDep`, `MemberActorDep` and `OptionalActorDep` in `identity/api/deps.py`
  are the single translation point.
- A context that must read another's tables uses a read port, never an ORM import. `identity`
  and `network` use raw `text()` queries (`infrastructure/member_directory.py` in each);
  `paths` uses the metadata-free `sqlalchemy.table()` handles in
  `paths/infrastructure/_member_tables.py`, which carry no metadata so Alembic never sees a
  second mapping of the members tables.
- An `api/` module may compose two contexts into one response, and no other layer may:
  `members/api/ask.py` puts the Paths flow on a members Ask answer, over the whole match set
  rather than the page.

## Authentication and authorization

Supabase Auth (Google, `cdtm.com` Workspace) issues the token; the API verifies it on every
request. There is no session, no cookie and no password anywhere in this codebase.

`SupabaseJwtVerifier` branches on the token header's `alg`: `HS*` against
`SUPABASE_JWT_SECRET`, anything else against the project's JWKS. Supabase projects exist in
both configurations, so both are supported.

Four dependencies, in increasing strictness. Pick the weakest one that is correct:

| Dependency | Requires | Use for |
| --- | --- | --- |
| `OptionalPrincipalDep` | nothing | endpoints that vary by viewer but do not require one |
| `PrincipalDep` | a valid token from an allowed domain | reads |
| `MemberPrincipalDep` | that, plus an Account bound to a Member | writes to member-owned data |
| `AdminPrincipalDep` | that, plus `is_admin` | account binding, admin promotion |

An Account with no bound Member is a normal state, not an error: about 175 roster rows have no
Workspace account at all and some Workspace accounts match no roster row (ADR 0001).
`MemberPrincipalDep` turns the write attempt into a 403 carrying a hint rather than a confusing
empty result.

### Local sign-in

There is no Supabase project yet, so nothing can issue the token the API expects. Rather than
add a second way in, a development-only endpoint mints one locally and then walks the ordinary
path with it: the same HS256 secret, the same `SupabaseJwtVerifier`, the same
`AuthService.authenticate`, the same account upsert and roster binding.

```bash
echo 'AUTH_DEV_LOGIN_ENABLED=true' >> .env    # needs SUPABASE_JWT_SECRET set too
uv run poe api

curl -s localhost:8000/api/v1/auth/dev/members?q=anna       # pick someone to be
curl -s localhost:8000/api/v1/auth/dev/login \
  -H 'content-type: application/json' \
  -d '{"email":"you@cdtm.com","member_slug":"anna-test"}'   # -> access_token + me
```

| Method | Path | |
| --- | --- | --- |
| `POST` | `/auth/dev/login` | `{email, member_slug?}` -> `{access_token, token_type, expires_in, me}` |
| `GET` | `/auth/dev/members` | `q` matches name or slug; up to 20 rows for the picker |

- The flag is off by default and refused in production. `create_app()` raises at boot if
  `AUTH_DEV_LOGIN_ENABLED` is set while `APP_ENVIRONMENT=production`, and again if the flag is
  set with no `SUPABASE_JWT_SECRET` to sign with. With the flag off the routes are not
  registered at all, so they are absent from `openapi.json` rather than merely a 404.
- `member_slug` is how you become someone. About 175 roster rows have no Workspace e-mail, so
  signing in as yourself leaves you bound to nobody. Passing a slug writes your address onto
  that Member first, which binds you to it. A Member already claimed by a *different* address
  is a 409, never an overwrite.
- The allow-list still applies. `outsider@gmail.com` is a 403 here exactly as it is on
  `/auth/me`, and it is checked before anything is written.
- `sub` is `uuid5(fixed namespace, email)`, so signing in twice with one address reaches one
  `accounts` row, the way a real Supabase `sub` would.
- `/auth/dev/members` needs no token. It feeds the picker you use before you have one.

Finer rules live in the services, never in routers: only the target of an intro request may
accept it, only the requester may withdraw it, only the organiser or an admin may edit an
event, only the owner or an admin may edit a housing listing. `MemberService._redact` strips
`email` from anyone not looking at themselves and hides an Entry whose `visibility` is
`hidden`.

## API surface

Everything below is under `APP_API_PREFIX` (default `/api/v1`), except `/` and `/health`.

### Identity

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/auth/me` | signed in |
| `POST` | `/auth/accounts/{account_id}/bind` | admin |
| `POST` | `/auth/accounts/{account_id}/admin` | admin |
| `POST` | `/auth/dev/login` | none, and only with `AUTH_DEV_LOGIN_ENABLED` |
| `GET` | `/auth/dev/members` | none, and only with `AUTH_DEV_LOGIN_ENABLED` |

### Media

Uploads go through the API because the Storage buckets are private; the URL that comes back
is what belongs in `jobs.image_url` or `housing_listings.photo_urls`. See
[`../docs/architecture.md`](../docs/architecture.md) section 9.

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `POST` | `/media/{kind}` | signed in | `kind` is `job-image`, `housing-photo` or `avatar`; multipart `file`; 201 with `{url, bucket, key, content_type, size}` |
| `GET` | `/media/{bucket}/{key}` | none | the key is the access control; streams locally, 307s to a signed URL on Supabase |
| `DELETE` | `/media/{bucket}/{key}` | admin | no blob has a recorded owner yet |

JPEG, PNG and WebP only, decided by the magic bytes rather than the declared type (422
otherwise), and at most `STORAGE_MAX_UPLOAD_BYTES` (413 otherwise).

### Members: the directory

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/members/` | `q`, `class_id`, `class_label`, `major`, `role`, `location`, `company`, repeatable `intent` and `skill`, `is_ca`, `has_entry`, `claimed_only`, `needs_review` (admin only), `skip`, `limit` |
| `GET` | `/members/lookup` | repeatable `ids`, up to 50; cards for the authors behind other boards' rows |
| `GET` | `/members/at-company` | repeatable `company`, up to 50; one member per company name, with the full count |
| `GET` | `/members/facets` | classes, majors, total |
| `GET` | `/members/{slug}` | full profile; `email` to self or admin, `review` to admin only |

### Members: what I maintain

| Method | Path |
| --- | --- |
| `GET` | `/members/me` |
| `GET` `PUT` | `/members/me/entry` |
| `GET` `PUT` | `/members/me/intents` |

### Network: saved people and intros

| Method | Path |
| --- | --- |
| `GET` | `/network/saved` |
| `PUT` `DELETE` | `/network/saved/{member_id}` |
| `GET` `POST` | `/network/intros` |
| `POST` | `/network/intros/{request_id}/respond` |

### Events, announcements, housing, paths

| Method | Path | Notes |
| --- | --- | --- |
| `GET` `POST` | `/events/` | `upcoming` defaults to true |
| `GET` `PATCH` `DELETE` | `/events/{event_id}` | organiser or admin |
| `PUT` | `/events/{event_id}/rsvp` | `null` status clears it |
| `GET` `POST` | `/announcements/` | list carries an `unread` count; create is admin |
| `GET` `PATCH` `DELETE` | `/announcements/{announcement_id}` | admin |
| `POST` | `/announcements/{announcement_id}/read` | |
| `GET` `POST` | `/housing/` | `kind`, `city`, `status`, `member_id`, `furnished` |
| `GET` `PATCH` `DELETE` | `/housing/{listing_id}` | owner or admin; a `GET` by anyone else counts a view |
| `POST` | `/housing/{listing_id}/renew` | another 60 days, and reopens a closed listing |
| `GET` | `/paths/flow` | nodes and links for the Sankey view |
| `GET` | `/paths/groups` | group names per stage, including `intent` |
| `GET` | `/paths/members` | `stage` (`study`, `first_step`, `current`) and `group` |
| `GET` | `/paths/members/{slug}` | that member's career path |

### Ask

One per board, each with `/explain` (the interpretation without the answer) and `/schema` (the
filter object and the values it accepts). All three take an optional `language` for the summary.

| Method | Path |
| --- | --- |
| `POST` | `/members/ask/`, `/housing/ask/`, `/jobs/ask/` |
| `POST` | `/members/ask/explain`, `/housing/ask/explain`, `/jobs/ask/explain` |
| `GET` | `/members/ask/schema`, `/housing/ask/schema`, `/jobs/ask/schema` |

A members answer carries the Paths flow drawn over every member the question matched, not just
the page. See [`../docs/ask.md`](../docs/ask.md).

### Job board

Mounted without a prefix of its own, so the paths the standalone job board published are
unchanged.

| Method | Path |
| --- | --- |
| `GET` `POST` | `/companies/`, `/jobs/`, `/seekers/` |
| `GET` | `/companies/slug/{slug}`, `/jobs/slug/{slug}` |
| `GET` `PATCH` `DELETE` | `/companies/{id}`, `/jobs/{id}`, `/seekers/{id}` |

`POST /jobs` and `POST /seekers` set `posted_by_member_id` and `member_id` from the caller
themselves. Neither id is part of a request body, so a job cannot be attributed to someone
else. That join is what ADR 0002 exists for.

### Shapes

Every list takes `skip` and `limit` (capped at 100) and returns `{items, total}`. Every error
is `{"error": {"code", "message", "ref"}}` with the same `ref` in the `X-Error-ID` header.
`PATCH` bodies use optional fields, so an unset field is left alone rather than nulled.

## Settings

One class per concern, each `lru_cache`d through `settings_cache`, all reading the same env
files: the repository-root `.env`, then `backend/core/.env` if present. The process
environment wins over the files.

| Class | Prefix | Notable keys |
| --- | --- | --- |
| `AppSettings` | `APP_` | `ENVIRONMENT`, `DEBUG`, `API_PREFIX`, `CORS_ORIGINS` (comma-separated), `FRONTEND_URL`, `PUBLIC_BASE_URL` |
| `DatabaseSettings` | `DATABASE_` | `URL`, `MIGRATOR_URL`, `POOL_SIZE`, `MAX_OVERFLOW`, `STATEMENT_TIMEOUT_MS`, `ECHO` |
| `AuthSettings` | `AUTH_` | `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `AUTH_JWT_AUDIENCE`, `AUTH_ALLOWED_EMAIL_DOMAINS`, `AUTH_ADMIN_EMAILS`, `AUTH_JWKS_CACHE_SECONDS`, `AUTH_DEV_LOGIN_ENABLED` |
| `StorageSettings` | `STORAGE_` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_AVATARS_BUCKET`, `STORAGE_BACKEND`, `STORAGE_LOCAL_DIR`, `STORAGE_MAX_UPLOAD_BYTES` |

Behaviours worth knowing:

- `create_app()` resolves all four at boot, so a misconfigured deployment crashes at startup
  rather than on the first request that happens to need the missing value.
- `env_ignore_empty=True` means a template line such as `SUPABASE_JWT_SECRET=` reads as unset.
  Without it the empty string would validate and the API would accept tokens signed with
  nothing.
- `SUPABASE_URL`, `SUPABASE_JWT_SECRET` and `SUPABASE_SERVICE_ROLE_KEY` are aliases, so they
  are spelled without a prefix even though they belong to prefixed classes. They are the names
  Supabase itself uses, and renaming them would guarantee a copy-paste mistake.
- `APP_ENVIRONMENT=production` turns off `/docs`, `/redoc` and `/openapi.json`. Generate the
  client from the committed `frontend/openapi/openapi.json` instead.

## Errors

`backend/core/exceptions.py` is the whole vocabulary:

| Raise | HTTP | `code` |
| --- | --- | --- |
| `ValidationError` | 422 | `validation_error` |
| `UnauthorizedError` | 401 | `unauthorized` |
| `ForbiddenError` | 403 | `forbidden` |
| `NotFoundError` | 404 | `not_found` |
| `ConflictError` | 409 | `conflict` |
| `PayloadTooLargeError` | 413 | `payload_too_large` |
| `RepositoryError` | 503 | `storage_unavailable` |
| `AppError` | 500 | `internal_error` |

Below 500 the message you pass is shown to the caller, so write it for a person. At or above
500 it is replaced with "Something went wrong" and logged with a stack trace. Every response
carries a fresh `ref`, in the body and in `X-Error-ID`, and the same `ref` is in the log line.

Routers do not catch domain errors. `run_db` in `infrastructure/repository.py` is the only
place a driver exception is handled.

## Tests

Two lanes, marked so they cannot be confused (`--strict-markers` turns a typo into a
collection error):

```bash
uv run poe test-fast          # tests/unit: settings, AuthService with fake ports, classifier
uv run poe test-integration   # tests/integration: real app, real local Postgres
```

The integration suite is not mocked. It builds the real app with `TestClient`, runs
`alembic upgrade head` once per session, and `TRUNCATE`s every table before every test. What
makes that safe and repeatable:

- A loopback guard. `require_local_database` refuses any host that is not `localhost`,
  `127.0.0.1` or `::1`, and fails closed on a host-less URL. An exported Supabase
  `DATABASE_URL` is a plausible accident and this is what stops it wiping a real database.
- Environment defaults are set before `backend` is imported, because settings are cached on
  first access.
- One session-scoped `TestClient`, because asyncpg pools are bound to the event loop that
  created them.

Tokens are minted locally: `mint_token(email)` in `conftest.py` signs a Supabase-shaped HS256
JWT with the test secret, and `auth(email)` returns the header. Fixtures `member_anna`,
`member_ben` and `admin_headers` cover the usual two-party cases.

`tests/integration/test_migrations.py` is the schema guard: it migrates a scratch database
from empty to head and asserts Alembic's `compare_metadata` against `Base.metadata` is empty.
Change an ORM model without a migration and it goes red.

## Scripts

```bash
uv run poe openapi          # scripts/platform/export_openapi.py
uv run poe load-community   # scripts/platform/load_community.py
uv run poe match-emails     # scripts/platform/match_workspace_emails.py
uv run poe seed             # scripts/platform/seed_dev_data.py
```

`export_openapi.py` forces `APP_ENVIRONMENT=development` so the schema never depends on a
production flag, and writes sorted with `indent=2` so a one-field change is a one-line diff.

`load_community.py` reads the output of `frontend/scripts/ingest.mjs` and upserts it. It makes
no matching decisions of its own (ADR 0004); `matched`, `match_method` and `needs_review` come
through as data. It does compute each Member's career path.

```bash
uv run poe load-community \
  --index frontend/public/data/index.json \
  --profiles frontend/public/profiles \
  --emails data/derived/workspace-emails.csv        # slug,email
```

`match_workspace_emails.py` produces that CSV: it reads the Google Workspace export from
`data/workspace/` and matches it to members by name, sending anything ambiguous to a review
file instead of guessing.

`seed_dev_data.py` adds a few companies, jobs, an event, an announcement and a housing listing
around whatever members are already loaded. It is idempotent and keyed by slug or title.

## Conventions

- Python 3.11 or 3.12, `from __future__ import annotations` at the top of every module.
- ruff, line length 100, rules `F`, `I`, `UP`, `B`, `SIM`, `S`.
- Domain models are `extra="forbid"`, so a typo in a request body is a 422 rather than a
  silently ignored field.
- `XPublic` subclasses the domain model; `XsPublic` is `{items, total}`. Public schemas are the
  OpenAPI contract the frontend client is generated from.
- Comments explain *why*, and name the concrete reason. "PgBouncer in transaction mode cannot
  track prepared statements" beats "disable statement cache".

## See also

- [`../docs/architecture.md`](../docs/architecture.md): the system around this backend
- [`../docs/database-design.md`](../docs/database-design.md): the schema
- [`../infrastructure/README.md`](../infrastructure/README.md): engines and migrations
- One `CONTEXT.md` per context, which is where the domain language is defined:
  [`members`](members/CONTEXT.md), [`network`](network/CONTEXT.md), [`paths`](paths/CONTEXT.md),
  [`events`](events/CONTEXT.md), [`announcements`](announcements/CONTEXT.md),
  [`housing`](housing/CONTEXT.md), [`identity`](identity/CONTEXT.md),
  [`jobboard`](jobboard/CONTEXT.md)
