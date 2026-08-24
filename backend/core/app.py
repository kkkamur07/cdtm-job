"""FastAPI application factory.

Everything that is cross-cutting lives here: settings resolution at boot, the error
envelope, security headers, CORS and router registration. Bounded contexts only
export an ``APIRouter``; they never touch the app object.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Starlette's HTTPException, not FastAPI's subclass. The router raises the parent for a
# framework 404 or 405, and a handler registered on the subclass never sees those: they
# fell through to Starlette's default handler and answered {"detail": ...} with no error
# code, no ref and no log line. Registering the parent catches both.
from starlette.exceptions import HTTPException

import infrastructure.models  # noqa: F401 - register every ORM mapper before the first query
from backend.announcements.api.router import router as announcements_router
from backend.core.api.health import router as health_router
from backend.core.api.root import router as root_router
from backend.core.exceptions import AppError
from backend.core.schemas.errors import ErrorResponse
from backend.core.settings import (
    AppSettings,
    AuthSettings,
    get_app_settings,
    get_auth_settings,
    get_database_settings,
    get_storage_settings,
)
from backend.core.text import MAX_JSON_BODY_BYTES
from backend.events.api.router import router as events_router
from backend.housing.api.router import router as housing_router
from backend.identity.api.dev_router import router as dev_login_router
from backend.identity.api.router import router as identity_router
from backend.jobboard.api.router import router as jobboard_router
from backend.media.api.router import router as media_router
from backend.members.api.router import router as members_router
from backend.network.api.router import router as network_router
from backend.paths.api.router import router as paths_router
from infrastructure.db import get_async_engine

logger = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Not allowed"},
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    413: {"model": ErrorResponse, "description": "Payload too large"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    503: {"model": ErrorResponse, "description": "Storage unavailable"},
    500: {"model": ErrorResponse, "description": "Internal error"},
}

_HTTP_PUBLIC_MESSAGES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Not allowed",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    413: "Payload too large",
    415: "Unsupported media type",
    422: "Validation error",
    429: "Too many requests",
}


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    ref: str,
    headers: dict[str, str] | None = None,
    details: dict | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "ref": ref}}
    if details:
        body["error"]["details"] = details
    out_headers = {"X-Error-ID": ref}
    if headers:
        out_headers.update(headers)
    return JSONResponse(status_code=status_code, content=body, headers=out_headers)


def _correlated(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    exc: BaseException,
    details: dict | None = None,
) -> JSONResponse:
    ref = uuid.uuid4().hex
    log = logger.exception if status_code >= 500 else logger.warning
    log(
        "api_error ref=%s method=%s path=%s status=%s code=%s exception=%s",
        ref,
        request.method,
        request.url.path,
        status_code,
        code,
        type(exc).__name__,
    )
    return _error_response(
        status_code=status_code, code=code, message=message, ref=ref, details=details
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        # Messages from our own hierarchy are written to be shown; 5xx ones are not.
        message = exc.message if exc.status_code < 500 else "Something went wrong"
        return _correlated(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=message,
            exc=exc,
            details=exc.details or None,
        )

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        message = _HTTP_PUBLIC_MESSAGES.get(exc.status_code, "Request failed")
        ref = uuid.uuid4().hex
        logger.warning(
            "http_error ref=%s method=%s path=%s status=%s detail=%r",
            ref,
            request.method,
            request.url.path,
            exc.status_code,
            exc.detail,
        )
        return _error_response(
            status_code=exc.status_code,
            code=f"http_{exc.status_code}",
            message=message,
            ref=ref,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _correlated(
            request,
            status_code=422,
            code="validation_error",
            message="Validation error",
            exc=exc,
            # jsonable_encoder: a validation error over a non-JSON body (a form post, or
            # bytes) carries the raw input in ``errors()``, and json.dumps of bytes is a
            # TypeError, which turned every malformed body into a 500.
            details={"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return _correlated(
            request, status_code=500, code="internal_error", message="Something went wrong", exc=exc
        )


def _check_dev_login(app_settings: AppSettings, auth_settings: AuthSettings) -> None:
    """Refuse to boot with the development login on in production.

    ``/auth/dev/login`` hands a valid token to anyone who can name an address on an allowed
    domain, admins included. A deployment that reaches production with the flag set has to
    crash on startup: mounting it and hoping nobody finds it is not a control.
    """
    if not auth_settings.dev_login_enabled:
        return
    if app_settings.is_production:
        raise RuntimeError(
            "AUTH_DEV_LOGIN_ENABLED is set while APP_ENVIRONMENT=production. "
            "The development login mints tokens for any allowed e-mail; unset it."
        )
    if not auth_settings.jwt_secret:
        raise RuntimeError(
            "AUTH_DEV_LOGIN_ENABLED is set but SUPABASE_JWT_SECRET is empty. "
            "The development login signs with the same secret the verifier checks."
        )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_async_engine().dispose()


def create_app() -> FastAPI:
    # Resolve every settings object up front so a misconfigured deployment fails at boot,
    # not on the first request that happens to need the missing value.
    app_settings = get_app_settings()
    get_database_settings()
    auth_settings = get_auth_settings()
    get_storage_settings()
    _check_dev_login(app_settings, auth_settings)

    docs_enabled = not app_settings.is_production
    app = FastAPI(
        title="CDTM Community API",
        version="0.2.0",
        description="Member directory, network, events, housing and the job board.",
        lifespan=_lifespan,
        responses=COMMON_ERROR_RESPONSES,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    media_prefix = f"{app_settings.api_prefix}/media"
    # An upload is multipart, so its declared length is the file plus part headers. The
    # storage adapter still checks the bytes it actually read; this is only the early refusal.
    upload_limit = get_storage_settings().max_upload_bytes + 64 * 1024

    @app.middleware("http")
    async def _body_size_limit(request: Request, call_next):  # noqa: ANN001, ANN202
        """Refuse an oversized body before any handler reads it.

        Only ``Content-Length`` is checked, which is what every real client sends; a chunked
        request without one is left to the per-field ``max_length`` on the write models. The
        point is that nothing arrives with a megabyte of prose for a field the database is
        going to carry on every later read of that row.
        """
        declared = request.headers.get("content-length")
        if declared and declared.isdigit():
            limit = (
                upload_limit if request.url.path.startswith(media_prefix) else MAX_JSON_BODY_BYTES
            )
            if int(declared) > limit:
                ref = uuid.uuid4().hex
                logger.warning(
                    "body_too_large ref=%s method=%s path=%s bytes=%s limit=%s",
                    ref,
                    request.method,
                    request.url.path,
                    declared,
                    limit,
                )
                response = _error_response(
                    status_code=413,
                    code="payload_too_large",
                    message=f"Request body is larger than {limit} bytes",
                    ref=ref,
                )
                response.headers.update(SECURITY_HEADERS)
                return response
        return await call_next(request)

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):  # noqa: ANN001, ANN202
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Error-ID"],
    )
    _register_exception_handlers(app)

    app.include_router(root_router)
    app.include_router(health_router)
    prefix = app_settings.api_prefix
    app.include_router(identity_router, prefix=prefix)
    if auth_settings.dev_login_enabled:
        # Registered conditionally, not guarded inside the handler: an unmounted route is
        # also an absent one in the OpenAPI document the frontend client is generated from.
        app.include_router(dev_login_router, prefix=prefix)
    app.include_router(media_router, prefix=prefix)
    # One router per bounded context (ADR 0007), each mounted under its own path segment.
    app.include_router(members_router, prefix=prefix)
    app.include_router(network_router, prefix=prefix)
    app.include_router(paths_router, prefix=prefix)
    app.include_router(events_router, prefix=prefix)
    app.include_router(announcements_router, prefix=prefix)
    app.include_router(housing_router, prefix=prefix)
    app.include_router(jobboard_router, prefix=prefix)
    return app
