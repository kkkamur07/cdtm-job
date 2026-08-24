"""What an ``AppError`` carries: the message the caller is shown and the details beside it.

``core.app`` copies both into the JSON error envelope, so anything lost here is lost to
every client. Nothing else in the suite reads ``.message`` or ``.details``.
"""

from __future__ import annotations

import pytest

from backend.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitedError,
    RepositoryError,
    RetryableError,
    UnauthorizedError,
    ValidationError,
)


def test_the_callers_message_and_details_survive_construction() -> None:
    error = ValidationError("that city is not on the list", details={"field": "city"})
    assert error.message == "that city is not on the list"
    assert error.details == {"field": "city"}


def test_details_default_to_an_empty_mapping_not_none() -> None:
    # core.app does `exc.details or None`; a None here would be a TypeError on every raise.
    assert AppError("boom").details == {}


def test_a_message_less_error_reads_as_words_not_as_a_code() -> None:
    # The code is the machine-readable half of the envelope; the message is the human half,
    # so the fallback humanises it rather than repeating the identifier verbatim.
    assert NotFoundError().message == "not found"
    assert RepositoryError().message == "storage unavailable"
    assert PayloadTooLargeError().message == "payload too large"
    assert "_" not in RetryableError().message


def test_str_of_an_error_still_shows_something_greppable() -> None:
    assert str(NotFoundError()) == "not_found"
    assert str(NotFoundError("no such job")) == "no such job"


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (NotFoundError, 404, "not_found"),
        (ConflictError, 409, "conflict"),
        (ValidationError, 422, "validation_error"),
        (PayloadTooLargeError, 413, "payload_too_large"),
        (UnauthorizedError, 401, "unauthorized"),
        (ForbiddenError, 403, "forbidden"),
        (RepositoryError, 503, "storage_unavailable"),
        (RetryableError, 503, "retry_conflict"),
        (RateLimitedError, 429, "rate_limited"),
    ],
)
def test_every_error_keeps_the_status_and_code_clients_branch_on(
    error: type[AppError], status_code: int, code: str
) -> None:
    # These are class-body constants that mutation testing never touches, and they are the
    # contract the frontend switches on.
    assert (error.status_code, error.code) == (status_code, code)
