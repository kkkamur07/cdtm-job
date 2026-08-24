# CDTM Community documentation

The Community Tool is the central place to connect the CDTM community more effectively: find
people quickly, start collaborations, and turn shared interests into action, whether that is
founding, mentoring, hiring, speaking, or hobbies. The goal is clear value, low friction, and
a reason to come back.

Start with the document that matches what you are about to do.

| Doc | Read it when |
| --- | --- |
| [Root README](../README.md) | You want the product overview and a quick start |
| [Technical architecture](architecture.md) | You want the system design, bounded contexts, auth flow, error model, or deployment |
| [Database design](database-design.md) | You want the schema, an index, the Supabase connection rules, or the migration workflow |
| [Ask](ask.md) | You are working on the natural-language Ask boxes, or configuring a model provider |
| [Performance pass, 2026-08-24](performance-pass-2026-08-24.md) | You want the before/after numbers, what each audit found, what was implemented, what was validated and skipped, and the open decisions |
| [Mutation testing](mutation-testing.md) | You want to know how strong the tests are, run mutmut on a slice of the backend, or read what the first campaign found |
| [Backend README](../backend/README.md) | You are writing a route, a service or a repository |
| [Infrastructure README](../infrastructure/README.md) | You are writing or applying a migration |

## Decisions

Architecture Decision Records live in [`adr/`](adr/README.md). Read them when you want to know
why something is the way it is, before proposing that it be otherwise.

| # | Title |
| --- | --- |
| [0001](adr/0001-google-workspace-account-is-the-identity.md) | The Google Workspace account is the identity |
| [0002](adr/0002-one-backend-for-community-and-job-board.md) | One backend for the Community Tool and the job board |
| [0003](adr/0003-sqlalchemy-and-alembic-against-supabase-postgres.md) | SQLAlchemy and Alembic straight against Supabase Postgres |
| [0004](adr/0004-ingest-stays-a-node-script-loader-in-python.md) | Ingest stays a Node script; the loader is Python |
| [0005](adr/0005-member-entry-is-separate-from-the-scrape.md) | A Member's Entry is separate from the scrape |
| [0006](adr/0006-natural-language-ask-translates-to-filters.md) | A question is translated into filters, never into a query |
| [0007](adr/0007-bounded-contexts-follow-the-product-boards.md) | Bounded contexts follow the product's boards, not the old apps |

## Domain language

The vocabulary each bounded context uses, and the words it deliberately avoids:

- [`../CONTEXT-MAP.md`](../CONTEXT-MAP.md): the eight contexts and how they relate
- [`../backend/members/CONTEXT.md`](../backend/members/CONTEXT.md): Member, Roster, Class, Center Assistant, Entry
- [`../backend/network/CONTEXT.md`](../backend/network/CONTEXT.md): Saved member, Intro request
- [`../backend/paths/CONTEXT.md`](../backend/paths/CONTEXT.md): Member path, Stage, Group, Flow
- [`../backend/events/CONTEXT.md`](../backend/events/CONTEXT.md): Event, RSVP
- [`../backend/announcements/CONTEXT.md`](../backend/announcements/CONTEXT.md): Announcement, Read receipt
- [`../backend/housing/CONTEXT.md`](../backend/housing/CONTEXT.md): Listing, Kind, Renew
- [`../backend/identity/CONTEXT.md`](../backend/identity/CONTEXT.md): Account, Principal, Admin, binding
- [`../backend/jobboard/CONTEXT.md`](../backend/jobboard/CONTEXT.md): Company, Job, Seeker

The six in the middle were one context called `community` until ADR 0007 split them along the
boards the product actually has.

## Backlog

Deferred work lives in the repository-root [`TODO.md`](../TODO.md). It is an internal backlog,
not a list of what the product does.
