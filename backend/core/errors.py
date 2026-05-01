"""Central error model for the backend.

**Exception types** — Used by services and mapped to HTTP in ``backend.api.error_handling``.

**``supabase_execute``** — Wraps PostgREST ``.execute()`` calls: turns ``APIError`` / ``HTTPError``
into the exceptions above so infrastructure stays thin and logs preserve ``__cause__``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from httpx import HTTPError
from postgrest.exceptions import APIError

T = TypeVar("T")


class NotFoundError(Exception):
    """Aggregate row missing for the given identifier (expected domain outcome, not a DB bug)."""


class RepositoryError(Exception):
    """Base class for persistence layer failures (Supabase client, Postgres via PostgREST)."""


class ConflictError(RepositoryError):
    """Conflicting write — typically unique constraint (duplicate slug, etc.). HTTP ~409."""


class ConstraintError(RepositoryError):
    """FK/check constraint violation or other integrity rule failure. HTTP ~400/422."""


class TransactionError(RepositoryError):
    """Transactional failure (batch/commit scope). Rare with REST-only calls; use when using SQL transactions."""


_PG_UNIQUE = "23505"
_PG_FOREIGN_KEY = "23503"
_PG_CHECK = "23514"
_PG_QUERY_CANCELED = "57014"


def _map_postgrest_error(operation: str, err: APIError) -> RepositoryError:
    parts = [str(x) for x in (err.code, err.message, err.details, err.hint) if x]
    blob = " ".join(parts).lower()
    msg = err.message or str(err)

    if (
        _PG_UNIQUE in blob
        or err.code == _PG_UNIQUE
        or "unique constraint" in blob
        or "duplicate key" in blob
    ):
        return ConflictError(f"{operation}: {msg}")
    if (
        _PG_FOREIGN_KEY in blob
        or _PG_CHECK in blob
        or err.code in (_PG_FOREIGN_KEY, _PG_CHECK)
        or "foreign key constraint" in blob
        or "violates check constraint" in blob
    ):
        return ConstraintError(f"{operation}: {msg}")
    if _PG_QUERY_CANCELED in blob or err.code == _PG_QUERY_CANCELED:
        return TransactionError(f"{operation}: {msg}")
    return RepositoryError(f"{operation}: {msg}")


def supabase_execute(operation: str, fn: Callable[[], T]) -> T:
    """Run a PostgREST ``.execute()`` chain and map failures to typed repository errors."""
    try:
        return fn()
    except APIError as e:
        raise _map_postgrest_error(operation, e) from e
    except HTTPError as e:
        raise RepositoryError(f"{operation}: HTTP transport failure") from e
