"""FastAPI application factory.

Everything that is cross-cutting lives here: settings resolution at boot, the error
envelope, security headers, CORS and router registration. Bounded contexts only
export an ``APIRouter``; they never touch the app object.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders

# Starlette's HTTPException, not FastAPI's subclass. The router raises the parent for a
# framework 404 or 405, and a handler registered on the subclass never sees those: they
# fell through to Starlette's default handler and answered {"detail": ...} with no error
# code, no ref and no log line. Registering the parent catches both.
from starlette.exceptions import HTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import infrastructure.models  # noqa: F401 - register every ORM mapper before the first query
from backend.announcements.api.router import router as announcements_router
from backend.core.api.health import router as health_router
from backend.core.api.root import router as root_router
from backend.core.exceptions import AppError
from backend.core.llm import aclose_shared_client
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
from backend.identity.api.deps import get_token_verifier
from backend.identity.api.dev_router import router as dev_login_router
from backend.identity.api.router import router as identity_router
from backend.jobboard.api.router import router as jobboard_router
from backend.media.api.router import router as media_router
from backend.media.infrastructure import get_blob_storage
from backend.members.api.router import router as members_router
from backend.network.api.router import router as network_router
from backend.paths.api.router import router as paths_router
from infrastructure.db import get_async_engine, log_resolved_urls

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


async def _warm_jwks() -> None:
    """Fetch the Supabase signing keys before the first request needs them.

    The JWKS fetch is synchronous ``urllib`` inside PyJWT, and it happens on whichever
    request first presents an asymmetric token. Doing it here means that request is not the
    one that pays for it. Best effort on purpose: a Supabase project that is briefly
    unreachable at boot must not stop the API from starting, and the first token will fetch
    the key set itself.
    """
    if not get_auth_settings().jwks_url:
        return
    try:
        await get_token_verifier().warm_jwks()
    except Exception:  # noqa: BLE001 - any failure here is survivable, and none is fatal
        logger.warning("jwks_prewarm_failed url=%s", get_auth_settings().jwks_url, exc_info=True)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _warm_jwks()
    try:
        yield
    finally:
        # The storage adapter holds an HTTP connection pool for the life of the process.
        await get_blob_storage().aclose()
        # So does the model adapters' client: one TLS session kept across questions.
        await aclose_shared_client()
        await get_async_engine().dispose()


class RequestGuards:
    """Refuse an oversized body on the way in; add the security headers and time it on the
    way out.

    These were two ``@app.middleware("http")`` functions, which is ``BaseHTTPMiddleware``:
    every request gets an anyio task group and the response is streamed through a memory
    object stream. One of these reads a single request header and the other edits the
    response's start message, so neither needs any of that. As one plain ASGI app they are
    also one wrapper instead of two, and the timing rides along on the same pass rather than
    paying for a third.
    """

    def __init__(
        self, app: ASGIApp, *, media_prefix: str, upload_limit: int, slow_request_ms: int
    ) -> None:
        self._app = app
        self._media_prefix = media_prefix
        self._upload_limit = upload_limit
        self._slow_request_ms = slow_request_ms

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        started = time.perf_counter()
        # One-element list rather than a nonlocal: the sender below is a closure handed to
        # the app, and this is the only thing it has to tell us back.
        status: list[int] = []
        send_secured = _security_header_sender(send, status)
        try:
            refusal = self._body_too_large(scope)
            if refusal is not None:
                await refusal(scope, receive, send_secured)
            else:
                await self._app(scope, receive, send_secured)
        finally:
            self._log_timing(scope, status=status, started=started)

    def _log_timing(self, scope: Scope, *, status: list[int], started: float) -> None:
        """One line per request: what it was, how it ended and how long it took.

        The path is the *route template* (``/api/v1/members/{slug}``), which FastAPI leaves
        on the scope once it has matched. Logging the raw path instead would make one log
        shape per member and no way to ask which endpoint is slow.

        Slow requests are INFO, the rest are DEBUG, so a default deployment logs only the
        ones somebody would have noticed and turning the logger down gives the whole picture
        without a redeploy. Timing runs in a ``finally``: a request that ended in an
        exception is exactly the one worth having a duration for.
        """
        duration_ms = (time.perf_counter() - started) * 1000
        route = scope.get("route")
        logger.log(
            logging.INFO if duration_ms >= self._slow_request_ms else logging.DEBUG,
            "request method=%s path=%s status=%s duration_ms=%.1f",
            scope.get("method"),
            getattr(route, "path", None) or scope.get("path", ""),
            status[0] if status else 0,
            duration_ms,
        )

    def _body_too_large(self, scope: Scope) -> JSONResponse | None:
        """The 413 to answer with, or ``None`` to let the request through.

        Only ``Content-Length`` is checked, which is what every real client sends; a chunked
        request without one is left to the per-field ``max_length`` on the write models. The
        point is that nothing arrives with a megabyte of prose for a field the database is
        going to carry on every later read of that row.
        """
        declared = Headers(scope=scope).get("content-length")
        if not declared or not declared.isdigit():
            return None
        path = scope.get("path", "")
        limit = self._upload_limit if path.startswith(self._media_prefix) else MAX_JSON_BODY_BYTES
        if int(declared) <= limit:
            return None
        ref = uuid.uuid4().hex
        logger.warning(
            "body_too_large ref=%s method=%s path=%s bytes=%s limit=%s",
            ref,
            scope.get("method"),
            path,
            declared,
            limit,
        )
        return _error_response(
            status_code=413,
            code="payload_too_large",
            message=f"Request body is larger than {limit} bytes",
            ref=ref,
        )


def _security_header_sender(send: Send, status: list[int]) -> Send:
    """Add the security headers to the response start, and note the status for the log line."""

    async def send_secured(message: Message) -> None:
        if message["type"] == "http.response.start":
            MutableHeaders(scope=message).update(SECURITY_HEADERS)
            status.append(int(message["status"]))
        await send(message)

    return send_secured


def create_app() -> FastAPI:
    # Resolve every settings object up front so a misconfigured deployment fails at boot,
    # not on the first request that happens to need the missing value.
    app_settings = get_app_settings()
    get_database_settings()
    auth_settings = get_auth_settings()
    get_storage_settings()
    _check_dev_login(app_settings, auth_settings)
    log_resolved_urls()

    docs_enabled = not app_settings.is_production
    app = FastAPI(
        title="CDTM Community API",
        version="0.2.0",
        description="Member directory, network, events, housing and the job board.",
        lifespan=_lifespan,
        # No default_response_class here on purpose. FastAPI 0.141 serialises a route's
        # return value straight to JSON bytes through pydantic whenever the route declares
        # a response_model or a return type, which every route in this app does, and it
        # deprecated ORJSONResponse for exactly that reason: setting one puts the route
        # back on the slower jsonable_encoder path.
        responses=COMMON_ERROR_RESPONSES,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    media_prefix = f"{app_settings.api_prefix}/media"
    # An upload is multipart, so its declared length is the file plus part headers. The
    # storage adapter still checks the bytes it actually read; this is only the early refusal.
    upload_limit = get_storage_settings().max_upload_bytes + 64 * 1024

    app.add_middleware(
        RequestGuards,
        media_prefix=media_prefix,
        upload_limit=upload_limit,
        slow_request_ms=app_settings.slow_request_ms,
    )
    # JSON compresses five to ten times over, and every list route ships tens of kilobytes
    # of it over the public internet. Below a kilobyte the header costs more than it saves.
    # Added after the guards and before CORS, so the order the request meets them is
    # CORS, gzip, guards: the security headers are set before anything compresses.
    app.add_middleware(GZipMiddleware, minimum_size=1000)
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
