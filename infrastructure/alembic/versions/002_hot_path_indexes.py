"""Indexes for the paths the platform actually walks.

Revision ID: 002_hot_path_indexes
Revises: 001_initial_schema
Create Date: 2026-08-24

Three kinds of index, all found by reading EXPLAIN of the real endpoints rather than by
guessing:

* Foreign keys nobody indexed. Postgres does not index the referencing side of a foreign
  key for you. ``announcement_reads.member_id`` and ``event_rsvps.member_id`` are read on
  every board load (the "have I read this" and "am I going" subqueries), and every one of
  these columns has an ``ON DELETE CASCADE`` or ``SET NULL`` that makes deleting a member
  scan the child table once per row without them.
* Ordering that did not match its index. The job board's default sort is ``created_at
  DESC`` but the only partial index was on ``published_at DESC``, so the default list sorted
  6,000 rows on every request. Announcements order by ``is_pinned DESC`` then
  ``coalesce(published_at, created_at) DESC``, which no plain column index can serve.
* One trigram index: ``members.current_company`` is matched with ILIKE '%term%' by the
  directory's company filter and by the Ask.

Every statement is CREATE INDEX CONCURRENTLY so a deploy against the live database does not
take a write lock on members or jobs, which means the migration cannot run inside a
transaction; ``autocommit_block`` is what lets Alembic step out of one. IF NOT EXISTS makes
the migration re-runnable after a CONCURRENTLY build that failed halfway and left an invalid
index behind. Nothing here drops an existing index.
"""

from __future__ import annotations

from alembic import op

revision = "002_hot_path_indexes"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


#: (name, table, body). The body is the parenthesised index definition plus any WHERE, so
#: the same tuples drive both directions.
INDEXES: tuple[tuple[str, str, str], ...] = (
    # ---- unindexed foreign keys ------------------------------------------------------
    ("ix_announcement_reads_member_id", "announcement_reads", "(member_id)"),
    ("ix_event_rsvps_member_id", "event_rsvps", "(member_id)"),
    ("ix_saved_members_saved_member_id", "saved_members", "(saved_member_id)"),
    ("ix_announcements_author_member_id", "announcements", "(author_member_id)"),
    ("ix_events_created_by_member_id", "events", "(created_by_member_id)"),
    ("ix_companies_created_by_member_id", "companies", "(created_by_member_id)"),
    # ---- orderings the board asks for ------------------------------------------------
    (
        "ix_jobs_published_created",
        "jobs",
        "(created_at DESC) WHERE status = 'published'",
    ),
    (
        "ix_announcements_board_order",
        "announcements",
        "(is_pinned DESC, coalesce(published_at, created_at) DESC)",
    ),
    ("ix_housing_listings_created_at", "housing_listings", "(created_at DESC)"),
    # ---- single-stage path filters ----------------------------------------------------
    # ``ix_member_paths_groups`` leads with study_group, so a filter on only the first step
    # or only the current group cannot use it.
    ("ix_member_paths_current_group", "member_paths", "(current_group)"),
    ("ix_member_paths_first_step_group", "member_paths", "(first_step_group)"),
    # ---- trigram ----------------------------------------------------------------------
    (
        "ix_members_current_company_trgm",
        "members",
        "USING gin (current_company gin_trgm_ops)",
    ),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, body in INDEXES:
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} {body}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _table, _body in reversed(INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
