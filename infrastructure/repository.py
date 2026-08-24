"""Shared helpers for SQLAlchemy repositories: driver error mapping and timestamps.

Every context's repository wraps DB calls in :func:`run_db` so application code only
ever sees the ``backend.core.exceptions`` hierarchy."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import (
    AppError,
    ConflictError,
    QueryTimeoutError,
    RepositoryError,
    RetryableError,
    ValidationError,
)

T = TypeVar("T")

#: Statement cancelled by ``statement_timeout``.
_QUERY_CANCELED = "57014"
#: Serialization failure and deadlock detected: the transaction lost a race, not a fault.
_RACE_LOST = frozenset({"40001", "40P01"})


def utc_now() -> datetime:
    return datetime.now(UTC)


def _pgcode(exc: SQLAlchemyError) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def run_db(
    op: str, fn: Callable[[], Awaitable[T]], *, session: AsyncSession | None = None
) -> T:
    """Execute ``fn`` and map driver errors onto the application error hierarchy.

    * unique violation (23505)            -> ConflictError (409)
    * other integrity errors (23xxx)      -> ValidationError (422)
    * statement timeout (57014)           -> QueryTimeoutError (504)
    * serialization/deadlock (40001,40P01)-> RetryableError (503)
    * syntax/undefined object (42xxx)     -> AppError (500), ours to fix
    * bad data for the type (22xxx)       -> AppError (500), ours to fix
    * connection/operational problems     -> RepositoryError (503)

    ``session`` is the session ``fn`` used. Pass it: a failed statement leaves an
    ``AsyncSession`` refusing every later statement with ``PendingRollbackError``, and the
    session is shared by every repository in the request. Without the rollback here, code
    that deliberately catches one of these errors and carries on (``AuthService.authenticate``
    suppresses a ConflictError so that sign-in still works when a roster row is already bound
    elsewhere) poisons the whole request, and every call after it answers 503.
    """
    try:
        return await fn()
    except SQLAlchemyError as exc:
        await _rollback(session)
        raise _mapped(op, exc) from exc


async def _rollback(session: AsyncSession | None) -> None:
    if session is None:
        return
    # The caller's error is the one worth reporting; a rollback that itself fails has
    # nothing left to report to and must not replace it.
    with contextlib.suppress(Exception):
        await session.rollback()


def _mapped(op: str, exc: SQLAlchemyError) -> AppError:
    code = _pgcode(exc) if isinstance(exc, DBAPIError) else None
    if isinstance(exc, IntegrityError):
        if code == "23505":
            return ConflictError(f"{op}: conflicts with an existing record")
        return ValidationError(f"{op}: violates a database constraint")
    if code == _QUERY_CANCELED:
        return QueryTimeoutError(f"{op}: the query took too long and was cancelled")
    if code in _RACE_LOST:
        return RetryableError(f"{op}: the database was busy with a conflicting write")
    if code and code[:2] in ("42", "22"):
        # 42xxx is a statement the database could not make sense of (undefined column,
        # syntax error) and 22xxx is a value that does not fit its type. Both mean the code
        # is wrong, not the infrastructure; filing them as 503 invites a retry of something
        # that can never succeed and hides the bug in the storage-outage bucket.
        return AppError(f"{op}: invalid statement or value ({code})")
    if isinstance(exc, OperationalError):
        return RepositoryError(f"{op}: database unavailable")
    return RepositoryError(f"{op}: database error")
