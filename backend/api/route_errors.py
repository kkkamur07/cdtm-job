"""Translate domain/repository errors into ``HTTPException`` for route handlers."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

from backend.core.errors import (
    ConflictError,
    ConstraintError,
    NotFoundError,
    RepositoryError,
    TransactionError,
)


def rethrow_as_http(exc: Exception) -> NoReturn:
    """Convert known errors to HTTP responses; unknown errors become 500."""
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ConstraintError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, TransactionError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, RepositoryError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc
