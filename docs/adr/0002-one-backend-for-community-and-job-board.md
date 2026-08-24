# 0002. One backend for the Community Tool and the job board

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: process and repository topology, and the boundary between the two
  products inside it. It does not cover the persistence technology
  (see [0003](./0003-sqlalchemy-and-alembic-against-supabase-postgres.md)).

## Context

Two apps lived side by side in this repository with nothing between them:

- `jobboard/`: FastAPI over supabase-py, its own `pyproject.toml`, its own Supabase project,
  its own Next.js frontend, `companies` / `jobs` / `seekers`.
- `communitytool/`: a static Next.js export with no server and no database, reading JSON files
  produced by `scripts/ingest.mjs`, behind a shared-password gate.

They target the same people. A Member who posts a job is the same human as the Member in the
directory, and the job board had no way to know that: `Seeker` and `Member` were unrelated
rows in unrelated systems. The old `CONTEXT-MAP.md` said so in as many words ("independent
apps today; they share no code or data").

Both products also needed the same three things that neither had: a real login, a database
that can be written to, and a single OpenAPI contract for one frontend.

## Decision

One FastAPI application, one database, one deployment. Inside it, four bounded contexts under
`backend/`, each with the same four layers (`api/`, `application/`, `domain/`,
`infrastructure/`):

| Context     | Owns                                                                       |
| ----------- | -------------------------------------------------------------------------- |
| `core`      | The app factory, settings, the exception hierarchy, pagination, `/health`   |
| `identity`  | `accounts`, JWT verification, the `Principal` dependency                    |
| `community` | Members, Entries, Intents, network, events, announcements, housing, paths   |
| `jobboard`  | Companies, jobs, seekers                                                    |

The job board keeps its `/api/v1/{companies,jobs,seekers}` paths and its `{items, total}`
response shape verbatim. Its router is mounted without a prefix of its own, so the URLs a
client already knows do not move.

The contexts talk in one direction only:

- `identity` is imported by the others for `PrincipalDep` and friends. It knows nothing about
  them.
- `community` publishes `Actor` (member id + admin flag) so its services never import
  `Principal`; `backend/community/api/deps.py` is the single translation point.
- `jobboard` references `members.id` from `jobs.posted_by_member_id` and `seekers.member_id`,
  both nullable and both `ON DELETE SET NULL`. A job board that outlives the directory still
  works.
- `identity` reads `members` for the e-mail binding, through a two-query `SqlMemberDirectory`
  written in raw SQL rather than by importing community's ORM.

## Rationale

The value of the merge is the join. "This job was posted by someone in your class" and
"this Member is open to roles" are the features that made the job board worth keeping, and
they are a foreign key away in one database, an integration project in two.

One login, not two. Building Supabase Auth twice, and reconciling two account tables, costs
more than the isolation is worth for a tool with roughly 1,400 users.

Separate contexts, not separate services. The two products have genuinely different
vocabularies (a Seeker is not a Member; a Company is not an employer of record), so they get
separate domain models, separate services and separate tables. What they share is a process
and a transaction boundary. That is a package boundary, and packages are free.

Alternatives considered:

- *Two services, one database.* Rejected: two deploys, two settings surfaces, two OpenAPI
  documents to stitch into one frontend, and the shared database still couples them.
- *Two services, two databases, sync by webhook.* Rejected outright at this scale. It buys
  independent failure domains that nobody asked for and pays with eventual consistency in the
  one place (who posted this) where users expect none.
- *Fold the job board into `community`.* Rejected: it would put `Job` and `Member` in one
  vocabulary and lose the contract the existing job board clients depend on.

## Consequences

- One `pyproject.toml`, one virtualenv, one `uv run poe` task list, one Alembic history for
  the whole platform.
- One CORS origin list, one error envelope, one set of security headers. `backend/core/app.py`
  is the only file that knows the app object exists.
- A router in any context can require a `Principal`, so the job board is now authenticated
  where it used to be open. `POST /api/v1/jobs` fills `posted_by_member_id` from the caller
  when the body leaves it unset.
- `backend/jobboard/` and `backend/community/` must not import each other. Nothing enforces
  that today except review; the FK columns are the only intended coupling.
- The legacy `jobboard/` and `communitytool/` directories are retired. They stay on disk only
  until the frontend port is finished, and they are excluded from ruff (`extend-exclude`).
