"""What the application factory wires up: where routes live, what is documented, what CORS
allows, and the early refusal of an oversized body.

Every assertion here is something a client can see: a URL, the OpenAPI document the
frontend client is generated from, a CORS response header, a 413. The app is built per
test rather than reused, because that is the only way to see what a different environment
or a different prefix produces.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.app import create_app
from backend.core.settings import get_storage_settings, reset_settings_caches
from backend.core.text import MAX_JSON_BODY_BYTES

SECRET = "unit-test-secret-at-least-32-bytes-long"


def _client(app: FastAPI) -> TestClient:
    """A client that never runs the lifespan: nothing here needs the database, and the
    shutdown hook disposes the engine the integration suite is holding open."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    reset_settings_caches()
    yield
    reset_settings_caches()


def _env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """A complete, explicit environment: no developer's .env may decide these assertions."""
    values = {
        "APP_ENVIRONMENT": "development",
        "APP_API_PREFIX": "/api/v1",
        "APP_CORS_ORIGINS": "http://localhost:3000",
        "AUTH_DEV_LOGIN_ENABLED": "false",
        "SUPABASE_JWT_SECRET": SECRET,
        "STORAGE_BACKEND": "local",
        **overrides,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    reset_settings_caches()


def _paths(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> set[str]:
    _env(monkeypatch, **overrides)
    return set(create_app().openapi()["paths"])


def test_every_context_is_mounted_under_the_configured_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-default prefix: a router mounted without one would answer at "/members/" and
    # the generated frontend client would call a URL that does not exist.
    paths = _paths(monkeypatch, APP_API_PREFIX="/api/v9")
    for segment in (
        "auth",
        "media",
        "members",
        "network",
        "paths",
        "events",
        "announcements",
        "housing",
        "jobs",
    ):
        assert any(p.startswith(f"/api/v9/{segment}") for p in paths), segment
    assert not any(p.startswith("/api/v1/") for p in paths)


def test_health_stays_off_the_prefix_so_a_probe_never_has_to_know_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "/health" in _paths(monkeypatch)


def test_the_development_login_is_mounted_only_when_it_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unmounted, not guarded inside the handler: an absent route is also absent from the
    # OpenAPI document the frontend client is generated from.
    assert "/api/v1/auth/dev/login" not in _paths(monkeypatch)
    assert "/api/v1/auth/dev/login" in _paths(monkeypatch, AUTH_DEV_LOGIN_ENABLED="true")


def test_the_document_names_the_service_and_its_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    info = create_app().openapi()["info"]
    assert info["title"] == "CDTM Community API"
    assert info["version"] == "0.2.0"
    assert info["description"] == "Member directory, network, events, housing and the job board."


def test_the_docs_are_served_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    client = _client(create_app())
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_production_publishes_no_schema_and_no_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, APP_ENVIRONMENT="production")
    client = _client(create_app())
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    # The API itself is still there; only its documentation is not.
    assert client.get("/health").status_code in (200, 503)


def test_cors_answers_the_frontend_and_nobody_else(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, APP_CORS_ORIGINS="https://app.example.test")
    client = _client(create_app())
    preflight = client.options(
        "/api/v1/members/",
        headers={
            "Origin": "https://app.example.test",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://app.example.test"
    allowed = {m.strip() for m in preflight.headers["access-control-allow-methods"].split(",")}
    assert {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} <= allowed
    assert preflight.headers["access-control-allow-credentials"] == "true"
    allowed_headers = {
        h.strip().lower() for h in preflight.headers["access-control-allow-headers"].split(",")
    }
    assert {"authorization", "content-type"} <= allowed_headers

    denied = client.options(
        "/api/v1/members/",
        headers={
            "Origin": "https://evil.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers


def test_the_error_reference_is_readable_from_the_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, APP_CORS_ORIGINS="https://app.example.test")
    client = _client(create_app())
    r = client.get("/api/v1/members/", headers={"Origin": "https://app.example.test"})
    assert r.status_code == 401
    exposed = {h.strip().lower() for h in r.headers["access-control-expose-headers"].split(",")}
    # Without this the ref in the envelope is invisible to the frontend's fetch wrapper.
    assert "x-error-id" in exposed


def test_an_upload_sized_body_is_allowed_only_on_the_media_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    upload_limit = get_storage_settings().max_upload_bytes + 64 * 1024
    client = _client(create_app())
    # A full-size photo plus its multipart headers is not refused before the handler.
    allowed = client.post(
        "/api/v1/media/avatar", headers={"content-length": str(upload_limit)}, content=b"x"
    )
    assert allowed.status_code != 413
    # One byte more is refused, and the refusal still carries the security headers.
    refused = client.post(
        "/api/v1/media/avatar", headers={"content-length": str(upload_limit + 1)}, content=b"x"
    )
    assert refused.status_code == 413
    assert refused.json()["error"]["code"] == "payload_too_large"
    assert refused.headers["X-Content-Type-Options"] == "nosniff"
    assert refused.headers["X-Frame-Options"] == "DENY"

    # A JSON route gets the much smaller body budget, not the upload one.
    json_route = client.post(
        "/api/v1/members/me/entry",
        headers={"content-length": str(MAX_JSON_BODY_BYTES + 1)},
        content=b"x",
    )
    assert json_route.status_code == 413
    assert (
        client.post(
            "/api/v1/members/me/entry",
            headers={"content-length": str(MAX_JSON_BODY_BYTES)},
            content=b"x",
        ).status_code
        != 413
    )


def test_a_chunked_body_without_a_length_is_left_to_the_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    client = _client(create_app())
    # No Content-Length to read: the early refusal has nothing to decide on, and the
    # per-field limits on the write models take over.
    r = client.post(
        "/api/v1/members/me/entry",
        headers={"transfer-encoding": "chunked"},
        content=iter([b"{}"]),
    )
    assert r.status_code != 413
