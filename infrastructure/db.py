"""SQLAlchemy engine, session factory and declarative base.

Two engines exist:

* an **async** engine (``asyncpg``) used by the FastAPI app and repositories;
* a **sync** engine (``psycopg``) used by Alembic and scripts.

Both are built lazily from :class:`backend.core.settings.DatabaseSettings` so tests
can swap the URL before the first connection. Supabase's pooler in *transaction* mode
(Supavisor, port 6543) does not support prepared statements, so the async engine disables
asyncpg's statement cache there; session mode (port 5432, including on the pooler host) and
a direct connection are fine either way. See :func:`_is_transaction_pooled`.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from functools import lru_cache

from sqlalchemy import DateTime, MetaData, Text, create_engine, event, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, SessionTransaction, mapped_column

from backend.core.settings import get_database_settings

logger = logging.getLogger(__name__)

#: Supavisor's transaction-pooling port. Session mode on the same host is 5432.
TRANSACTION_POOLER_PORT = 6543

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every bounded context's ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---- column factories every context's tables repeat -----------------------------------
# Six contexts now declare tables, and a generated primary key or a "not null, default
# now()" timestamp spelled six slightly different ways is how a migration ends up
# disagreeing with the ORM. They live next to Base for the same reason Base does.


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def timestamp() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


def text_array() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))


def _port_of(url: str) -> int | None:
    try:
        return make_url(url).port
    except ArgumentError:
        # Not a URL SQLAlchemy can parse. Nothing here can say anything about it, and
        # guessing is what the substring match used to do.
        return None


def _is_transaction_pooled(url: str, *, override: bool) -> bool:
    """Is this connection going through a pooler in *transaction* mode?

    It matters for two things: prepared statements cannot survive a connection that is
    handed to somebody else between transactions, and a ``statement_timeout`` sent as a
    startup parameter may never reach Postgres.

    The old rule was "the host contains pooler.supabase.com", which is wrong in the case
    this deployment actually uses. Supabase publishes *both* modes on that host: port 5432
    is Supavisor in session mode, where the connection is held for the whole session and
    prepared statements are perfectly safe, and port 6543 is transaction mode, where they
    are not. Disabling asyncpg's statement cache on the session-mode port gave up query-plan
    reuse on every statement the API issues, for a hazard that was not there.

    So the signal is the port, plus ``DATABASE_POOLER_TRANSACTION_MODE`` for a deployment
    whose port does not say (something in front of the pooler, or a Supavisor on a port of
    its own). A URL with no port at all is a direct connection to the default 5432.
    """
    return override or _port_of(url) == TRANSACTION_POOLER_PORT


def _statement_timeout_per_transaction(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    """Re-arm ``statement_timeout`` at the start of every transaction on an app session.

    ``get_async_engine`` sends the timeout as an asyncpg *startup* parameter, which is a
    property of the physical connection. Under transaction pooling the physical connection
    is not ours: it is shared, it may have been opened by the pooler long before this
    process asked for it, and the startup parameter may never have been forwarded. ``SET
    LOCAL`` is scoped to the transaction, so it cannot leak onto the next tenant of the same
    connection either, which is exactly why it is not a ``SET SESSION``.

    Only installed when transaction mode is on: it is one extra statement per transaction,
    and in session mode the startup parameter already holds.
    """
    timeout_ms = int(get_database_settings().statement_timeout_ms)
    connection.exec_driver_sql(f"SET LOCAL statement_timeout = {timeout_ms}")


class _AppSession(Session):
    """The sync session class behind this app's ``AsyncSession``.

    A distinct class only so the statement-timeout listener above attaches here and not to
    every ``Session`` in the process, Alembic's and the scripts' included.
    """


class _AppAsyncSession(AsyncSession):
    sync_session_class = _AppSession


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    settings = get_database_settings()
    url = settings.async_url
    connect_args: dict[str, object] = {
        "server_settings": {
            "application_name": "cdtm-community-api",
            "statement_timeout": str(int(settings.statement_timeout_ms)),
        },
    }
    if _is_transaction_pooled(url, override=settings.pooler_transaction_mode):
        # A pooler in transaction mode hands the connection to somebody else between
        # transactions, so a prepared statement this process named is gone by the next one.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    engine = create_async_engine(
        url,
        echo=settings.echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=connect_args,
    )
    return engine


def _sync_statement_timeout_listener(*, enabled: bool) -> None:
    """Attach or detach the per-transaction timeout, without ever doing either twice."""
    installed = event.contains(_AppSession, "after_begin", _statement_timeout_per_transaction)
    if enabled and not installed:
        event.listen(_AppSession, "after_begin", _statement_timeout_per_transaction)
    elif installed and not enabled:
        event.remove(_AppSession, "after_begin", _statement_timeout_per_transaction)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    settings = get_database_settings()
    _sync_statement_timeout_listener(
        enabled=_is_transaction_pooled(
            settings.async_url, override=settings.pooler_transaction_mode
        )
    )
    return async_sessionmaker(
        get_async_engine(),
        class_=_AppAsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding one session per request.

    Repositories never commit; the application service owning the use case does,
    so a use case that touches several aggregates is one transaction.
    """
    async with get_session_factory()() as session:
        yield session


def get_sync_engine(url: str | None = None) -> Engine:
    """Sync engine for Alembic and one-off scripts (psycopg3)."""
    settings = get_database_settings()
    return create_engine(url or settings.sync_url, pool_pre_ping=True, future=True)


def safe_url(url: str) -> str:
    """A URL with the password removed, for a log line."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except ArgumentError:
        return "<unparseable database url>"


def log_resolved_urls() -> None:
    """Say once, at boot, which database each of the two engines will reach, and how many
    connections this process may take.

    ``DATABASE_MIGRATOR_URL`` is documented as "defaults to ``DATABASE_URL``", and an empty
    value in a ``.env`` template reads as unset (``env_ignore_empty``), so a deployment that
    meant to point Alembic at the direct connection and left the line blank silently migrates
    through whatever ``DATABASE_URL`` is. That is not changed here; it is only made visible,
    which is why the fallback is spelled out in words rather than left to be inferred from
    two URLs that happen to match.

    The pool budget is on the same line because it is the number that has to be multiplied
    by the worker count and compared against the pooler's own limit: ``--workers 4`` with
    ``pool_size + max_overflow`` of 10 is 40 connections, and Supabase's transaction pooler
    is not obliged to give them.
    """
    settings = get_database_settings()
    override = settings.migrator_url_override
    logger.info(
        "database runtime=%s transaction_pooled=%s pool=%s+%s(max %s per worker) migrator=%s (%s)",
        safe_url(settings.async_url),
        _is_transaction_pooled(settings.async_url, override=settings.pooler_transaction_mode),
        settings.pool_size,
        settings.max_overflow,
        settings.pool_size + settings.max_overflow,
        safe_url(settings.migrator_url),
        "DATABASE_MIGRATOR_URL"
        if override
        else "DATABASE_MIGRATOR_URL unset, migrator falls back to DATABASE_URL",
    )


def reset_engines() -> None:
    """Forget cached engines (tests call this after changing settings)."""
    get_async_engine.cache_clear()
    get_session_factory.cache_clear()
