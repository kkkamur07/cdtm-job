"""SQLAlchemy engine, session factory and declarative base.

Two engines exist:

* an **async** engine (``asyncpg``) used by the FastAPI app and repositories;
* a **sync** engine (``psycopg``) used by Alembic and scripts.

Both are built lazily from :class:`backend.core.settings.DatabaseSettings` so tests
can swap the URL before the first connection. Supabase's pooler (PgBouncer in
transaction mode, port 6543) does not support prepared statements, so the async
engine disables asyncpg's statement cache; the direct connection (port 5432) is
fine either way.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from functools import lru_cache

from sqlalchemy import DateTime, MetaData, Text, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.core.settings import get_database_settings

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


def _is_pooler_url(url: str) -> bool:
    return ":6543/" in url or "pooler.supabase.com" in url


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
    if _is_pooler_url(url):
        # PgBouncer (transaction mode) cannot track prepared statements.
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


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_async_engine(), expire_on_commit=False, autoflush=False)


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


def reset_engines() -> None:
    """Forget cached engines (tests call this after changing settings)."""
    get_async_engine.cache_clear()
    get_session_factory.cache_clear()
