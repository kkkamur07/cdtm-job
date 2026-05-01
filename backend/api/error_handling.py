"""HTTP layer: map ``backend.core.errors`` to status codes and log consistently."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.errors import (
    ConflictError,
    ConstraintError,
    NotFoundError,
    RepositoryError,
    TransactionError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach FastAPI handlers so domain/repository errors become JSON responses."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        logger.warning("Conflict: %s", exc, exc_info=exc)
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ConstraintError)
    async def constraint_handler(_request: Request, exc: ConstraintError) -> JSONResponse:
        logger.warning("Constraint violation: %s", exc, exc_info=exc)
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(TransactionError)
    async def transaction_handler(_request: Request, exc: TransactionError) -> JSONResponse:
        logger.error("Transaction failure: %s", exc, exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(RepositoryError)
    async def repository_handler(_request: Request, exc: RepositoryError) -> JSONResponse:
        logger.error("Repository error: %s", exc, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": str(exc)})
