"""The JSON error envelope, on a throwaway app that can raise anything on demand.

The live routes can only produce the errors their own code raises, so the two things that
matter most here have no coverage anywhere else: a 5xx message is replaced with a generic
one before it reaches the caller, and a 4xx message and its details are not.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

from backend.core.app import _register_exception_handlers
from backend.core.exceptions import AppError, ForbiddenError, NotFoundError, RepositoryError


class _LeakyError(AppError):
    """A 5xx whose message names an internal detail, the way a real one would."""

    status_code = 500
    code = "internal_error"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    _register_exception_handlers(app)

    @app.get("/forbidden")
    async def _forbidden() -> None:
        raise ForbiddenError("you are not on this listing", details={"listing": "abc"})

    @app.get("/missing")
    async def _missing() -> None:
        raise NotFoundError()

    @app.get("/leaky")
    async def _leaky() -> None:
        raise _LeakyError("connection to db-primary.internal:5432 refused as user cdtm_app")

    @app.get("/storage")
    async def _storage() -> None:
        raise RepositoryError("members.list: database unavailable")

    @app.get("/teapot")
    async def _teapot() -> None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})

    @app.get("/typed")
    async def _typed(count: int = Query()) -> dict[str, int]:
        return {"count": count}

    @app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("an unhandled bug with a revealing message")

    return TestClient(app, raise_server_exceptions=False)


def test_a_4xx_shows_the_message_and_details_it_was_raised_with(client: TestClient) -> None:
    r = client.get("/forbidden")
    assert r.status_code == 403
    error = r.json()["error"]
    assert error["code"] == "forbidden"
    assert error["message"] == "you are not on this listing"
    assert error["details"] == {"listing": "abc"}
    assert error["ref"] == r.headers["X-Error-ID"]


def test_details_are_left_out_entirely_when_there_are_none(client: TestClient) -> None:
    error = client.get("/missing").json()["error"]
    assert "details" not in error
    # The message-less form still says something a reader can use.
    assert error["message"] == "not found"


def test_a_5xx_message_never_reaches_the_caller(client: TestClient) -> None:
    r = client.get("/leaky")
    assert r.status_code == 500
    error = r.json()["error"]
    assert error["message"] == "Something went wrong"
    assert "db-primary.internal" not in r.text
    assert "cdtm_app" not in r.text
    # The code and the reference still identify it in the logs.
    assert error["code"] == "internal_error"
    assert error["ref"] == r.headers["X-Error-ID"]


def test_the_redaction_boundary_is_the_whole_5xx_range(client: TestClient) -> None:
    # A storage fault is a 5xx too, and its message names the operation and the store, so
    # it is replaced as well; the code is what tells the caller to come back later.
    r = client.get("/storage")
    assert r.status_code == 503
    assert r.json()["error"]["message"] == "Something went wrong"
    assert r.json()["error"]["code"] == "storage_unavailable"
    assert "members.list" not in r.text


def test_an_unhandled_exception_says_nothing_about_itself(client: TestClient) -> None:
    r = client.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"] == {
        "code": "internal_error",
        "message": "Something went wrong",
        "ref": r.headers["X-Error-ID"],
    }
    assert "revealing" not in r.text


def test_a_framework_error_keeps_the_headers_it_carries(client: TestClient) -> None:
    r = client.get("/teapot")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.headers["X-Error-ID"] == r.json()["error"]["ref"]
    assert r.json()["error"]["code"] == "http_401"


def test_a_validation_error_carries_the_field_that_failed(client: TestClient) -> None:
    r = client.get("/typed", params={"count": "seven"})
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Validation error"
    errors = error["details"]["errors"]
    assert any("count" in str(item["loc"]) for item in errors)


def test_every_error_reference_is_unique(client: TestClient) -> None:
    refs = {client.get("/missing").json()["error"]["ref"] for _ in range(3)}
    assert len(refs) == 3


def test_a_5xx_is_logged_with_its_traceback_and_a_4xx_is_not(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="backend.core.app"):
        ref_500 = client.get("/leaky").json()["error"]["ref"]
        ref_404 = client.get("/missing").json()["error"]["ref"]

    by_ref = {r.levelno: r for r in caplog.records if r.name == "backend.core.app"}
    assert logging.ERROR in by_ref, caplog.records
    assert logging.WARNING in by_ref
    error_record = by_ref[logging.ERROR]
    warning_record = by_ref[logging.WARNING]
    assert ref_500 in error_record.getMessage()
    assert ref_404 in warning_record.getMessage()
    # An unexpected failure is logged with the traceback; an expected 404 is not.
    assert error_record.exc_info is not None
    assert warning_record.exc_info is None
