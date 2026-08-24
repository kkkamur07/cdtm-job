"""Every table this application maps must have row level security on.

Not because the API relies on it (it connects as the table owner, and RLS does not apply to
owners), but because on Supabase the ``public`` schema is also published through PostgREST to
the ``anon`` and ``authenticated`` roles, and the frontend ships the publishable key. A table
that reaches production without RLS is readable from any browser with that key. ``001`` turns
it on for a hard-coded list of table names, which is exactly the kind of list that a new
bounded context is added without: this test compares that list against ``Base.metadata``, so
the omission is a red test rather than an open table.

It runs on the ordinary integration database, already migrated by the ``client`` fixture,
rather than on the migration suite's scratch database: the question is about the schema the
migrations produce, and there is only one of those.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import infrastructure.models  # noqa: F401 - every mapper, so Base.metadata is complete
from infrastructure.db import Base, get_sync_engine

pytestmark = pytest.mark.integration


def test_every_mapped_table_has_row_level_security_enabled(client: TestClient) -> None:
    mapped = sorted(t.name for t in Base.metadata.sorted_tables)
    assert mapped, "no tables in Base.metadata: the mappers did not register"

    engine = get_sync_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    select c.relname, c.relrowsecurity
                    from pg_class c
                    join pg_namespace n on n.oid = c.relnamespace
                    where n.nspname = 'public' and c.relkind = 'r'
                    """
                )
            ).all()
    finally:
        engine.dispose()

    rls = {name: enabled for name, enabled in rows}
    missing_from_database = [name for name in mapped if name not in rls]
    assert not missing_from_database, (
        f"mapped but not in the database: {missing_from_database}. "
        "The migration chain does not create these."
    )
    without_rls = sorted(name for name in mapped if not rls[name])
    assert not without_rls, (
        f"tables with row level security off: {without_rls}. Add them to DROP_ORDER in "
        "infrastructure/alembic/versions/001_initial_schema.py, or to a new migration that "
        "runs ALTER TABLE ... ENABLE ROW LEVEL SECURITY for them."
    )


def test_no_table_carries_a_policy_that_would_let_a_browser_read_it(client: TestClient) -> None:
    """RLS with no policies denies everything, which is the whole point of turning it on.

    A policy added later, for a reason that made sense at the time, is what would turn the
    directory into a public table again. Nothing in this platform is meant to have one: the
    API is the only reader and it connects as the owner.
    """
    engine = get_sync_engine()
    try:
        with engine.connect() as conn:
            policies = conn.execute(
                text("select schemaname, tablename, policyname from pg_policies")
            ).all()
    finally:
        engine.dispose()

    assert policies == [], f"unexpected RLS policies: {policies}"
