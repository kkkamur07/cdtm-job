# 0007. Bounded contexts follow the product's boards, not the old apps

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: how the backend and the frontend are divided into contexts, which
  tables each one owns, and how they are allowed to know about each other. It replaces the
  "community" context of ADR 0002 with six smaller ones; ADR 0002's decision to run one
  backend stands.

## Context

ADR 0002 put everything that used to be the Community Tool into one context called
`community`, next to `jobboard` (the old job board) and `identity`. That mirrored the two
applications being merged, which was the honest shape at the time. It stopped being honest
as soon as the platform grew features the Community Tool never had.

By the end of the build, `community` held the member directory, what members maintain about
themselves, the network (saved people, intro requests), events, announcements, housing, the
Paths read model and three Ask translators: eight aggregates, 1,200 lines of domain models,
one `ports.py` with nine protocols, one `CONTEXT.md` trying to define "Listing" next to
"Intro request". Housing and Paths each have their own page, their own language and their own
Ask box, and nothing in common with an RSVP. The name `community` had come to mean "the part
that is not jobs", which is not a domain.

## Decision

A context is one board of the product, or one cross-cutting concern, and nothing larger.

| Context | Owns | Language |
| --- | --- | --- |
| `core` | app factory, settings, errors, pagination, the LLM port and adapters | shared kernel, no domain words |
| `identity` | `accounts` | Account, Principal |
| `members` | `members`, `classes`, `member_classes`, `ca_details`, `positions`, `educations`, `member_entries`, `member_intents` | Member, Entry, Intent, Class, claimed |
| `network` | `saved_members`, `intro_requests` | Saved, Intro request |
| `paths` | `member_paths` | Study group, First step, Current group, Flow |
| `events` | `events`, `event_rsvps` | Event, RSVP |
| `announcements` | `announcements`, `announcement_reads` | Announcement, pinned, read |
| `housing` | `housing_listings` | Listing, offer, looking, expires, renew |
| `jobboard` | `companies`, `jobs`, `seekers` | Company, Job, Seeker |
| `media` | the storage buckets | upload, image |

Each has the same four layers (`api`, `application`, `domain`, `infrastructure`), its own
`CONTEXT.md`, its own router prefix (`/api/v1/<context>/...`) and its own frontend slice in
`frontend/src/features/<context>/`. The Ask translators live in the context whose board they
serve (`members`, `jobboard`, `housing`) on top of the LLM port in `core`.

How contexts may know about each other, and these are the only ways:

- Every context imports `identity`'s dependencies to learn who is calling, and turns the
  `Principal` into an `Actor` (member id, admin flag) at its own router.
- A row that belongs to a Member stores `member_id` and nothing else about them. Jobs, listings,
  events and announcements do not join to `members`; the UI resolves ids to names through
  `GET /api/v1/members/lookup`.
- `network` and `paths` need more than an id. They read the directory through a small read port
  implemented with `text()` queries (`MemberDirectory` for "does this member exist, what is
  their card"; `CareerHistorySource` for positions and educations), the way `identity` already
  reads `members.email`. Neither imports another context's ORM.
- `paths` is a read model. It is recomputed by the loader (`scripts/platform/load_community.py`
  calls `members` to import, then `paths` to classify) and on demand for one member; nothing
  in `members` knows the classifier exists.
- `members` and `jobboard` never import each other (unchanged from ADR 0002).

## Consequences

- One Alembic history and one database, unchanged. The tables do not move; only the code that
  owns them does. `infrastructure/models.py` imports every context's `orm_models` so Alembic
  sees them all.
- Ten `CONTEXT.md` glossaries instead of four, each short enough to read. `CONTEXT-MAP.md`
  draws the arrows above and is the only place a cross-context mapping is written down.
- API prefixes change before anyone depends on them: `/api/v1/community/members` becomes
  `/api/v1/members`, `/api/v1/community/housing` becomes `/api/v1/housing`, and so on. The
  OpenAPI client is regenerated; nothing is kept for compatibility, there is nothing to be
  compatible with.
- `me/*` splits by owner: `me/entry` and `me/intents` are `members`, `me/saved` and `me/intros`
  are `network`. Home-page composition (announcements, events, people, jobs) is the frontend's
  job, not a backend aggregate.
- More folders. Each context is small, and the cost of finding a file by its board is lower
  than the cost of a `community` package that has to be read end to end to understand one page.

## Alternatives considered

- Keep `community` and carve out only housing and paths. Smallest change, but the directory
  would still carry events and announcements, which share nothing with it but a member id.
- One `bulletin` context for events and announcements. Same actors and a similar publish
  lifecycle, but different words and different pages; two small contexts are easier to name
  than one vague one, and each is one aggregate.
- Paths inside `members`. It is derived from member data, but it has its own vocabulary, its
  own table, its own page and its own Ask; keeping it apart also keeps the classifier from
  growing roots in the import path.
