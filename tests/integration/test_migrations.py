"""The migration chain must reproduce ``Base.metadata`` exactly.

Migrates a *scratch* database from empty to head and asserts alembic's autogenerate
comparison against the ORM finds nothing. Add a column to an ORM model without a migration
and this goes red.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

import infrastructure.models  # noqa: F401
from backend.core.settings import get_database_settings, reset_settings_caches
from infrastructure.db import Base

pytestmark = pytest.mark.integration

_SCRATCH = "cdtm_community_migration_check"
_ALEMBIC_INI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../../infrastructure/alembic.ini"
)
_UNMANAGED_TABLES = frozenset({"alembic_version"})


def _with_database(url: str, database: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{database}", query=""))


def _run_ddl(url: str, statement: str) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(statement))
    finally:
        engine.dispose()


@pytest.fixture
def migrated_scratch_database() -> Iterator[str]:
    base_url = get_database_settings().migrator_url
    maintenance = _with_database(base_url, "postgres")
    scratch = _with_database(base_url, _SCRATCH)
    _run_ddl(maintenance, f'DROP DATABASE IF EXISTS "{_SCRATCH}" WITH (FORCE)')
    _run_ddl(maintenance, f'CREATE DATABASE "{_SCRATCH}"')
    previous = os.environ.get("DATABASE_MIGRATOR_URL")
    os.environ["DATABASE_MIGRATOR_URL"] = scratch
    reset_settings_caches()
    try:
        command.upgrade(Config(_ALEMBIC_INI), "head")
        yield scratch
    finally:
        if previous is None:
            os.environ.pop("DATABASE_MIGRATOR_URL", None)
        else:
            os.environ["DATABASE_MIGRATOR_URL"] = previous
        reset_settings_caches()
        _run_ddl(maintenance, f'DROP DATABASE IF EXISTS "{_SCRATCH}" WITH (FORCE)')


def test_migration_chain_matches_orm_metadata(migrated_scratch_database: str) -> None:
    def include_name(name, type_, parent_names) -> bool:  # noqa: ANN001
        return type_ != "table" or name not in _UNMANAGED_TABLES

    engine = create_engine(migrated_scratch_database)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={
                    "include_name": include_name,
                    "compare_type": True,
                    "compare_server_default": True,
                },
            )
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()
    assert diff == [], "Schema drift between migrations and ORM:\n" + "\n".join(
        repr(d) for d in diff
    )


def test_downgrade_to_base_is_clean(migrated_scratch_database: str) -> None:
    os.environ["DATABASE_MIGRATOR_URL"] = migrated_scratch_database
    reset_settings_caches()
    command.downgrade(Config(_ALEMBIC_INI), "base")
    engine = create_engine(migrated_scratch_database)
    try:
        with engine.connect() as conn:
            tables = (
                conn.execute(text("select tablename from pg_tables where schemaname = 'public'"))
                .scalars()
                .all()
            )
    finally:
        engine.dispose()
    assert set(tables) <= {"alembic_version"}
