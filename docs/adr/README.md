# Architecture decision records

One file per decision, named `NNNN-kebab-case-title.md`, numbered in the order the decision
was taken. A record is written when a choice is expensive to reverse: schema shape, identity
and credential design, which process owns which data, where a trust boundary sits.

Records are immutable once merged. A decision that is later reversed gets a new record that
supersedes the old one, and the old one gains a `Superseded by` line. Do not edit history.
The value of an ADR is that it says what was believed at the time, and why.

| #                                                                  | Title                                                            | Status   |
| ------------------------------------------------------------------ | ---------------------------------------------------------------- | -------- |
| [0001](0001-google-workspace-account-is-the-identity.md)           | The Google Workspace account is the identity                     | Accepted |
| [0002](0002-one-backend-for-community-and-job-board.md)            | One backend for the Community Tool and the job board             | Accepted |
| [0003](0003-sqlalchemy-and-alembic-against-supabase-postgres.md)   | SQLAlchemy and Alembic straight against Supabase Postgres        | Accepted |
| [0004](0004-ingest-stays-a-node-script-loader-in-python.md)        | Ingest stays a Node script; the loader is Python                 | Accepted |
| [0005](0005-member-entry-is-separate-from-the-scrape.md)           | A Member's Entry is separate from the scrape                     | Accepted |
| [0006](0006-natural-language-ask-translates-to-filters.md)        | A question is translated into filters, never into a query         | Accepted |
| [0007](0007-bounded-contexts-follow-the-product-boards.md)           | Bounded contexts follow the product's boards, not the old apps   | Accepted |
