"""Application exception hierarchy.

Domain and application code raise these; ``core.app`` maps them to JSON
``{"error": {"code", "message", "ref"}}`` responses. Nothing in ``domain`` or
``application`` imports FastAPI.
"""

from __future__ import annotations


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str | None = None, *, details: dict | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code.replace("_", " ")
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class PayloadTooLargeError(AppError):
    """The request body is larger than the endpoint accepts (uploads)."""

    status_code = 413
    code = "payload_too_large"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class RepositoryError(AppError):
    """Infrastructure failure talking to the database."""

    status_code = 503
    code = "storage_unavailable"


class RetryableError(RepositoryError):
    """The statement lost a race in the database: a serialization failure or a deadlock.

    Still a 503, because the advice is the same as for any storage fault (come back), but a
    distinct code, because nothing is down and the very same request would probably succeed.
    """

    code = "retry_conflict"


class QueryTimeoutError(AppError):
    """The database gave up on the statement (``statement_timeout``).

    Not a 503: the store is up and answering, this one query was too expensive. Saying so is
    what stops a caller retrying it on a loop, which is the worst thing to do to a database
    that is already struggling with the query.
    """

    status_code = 504
    code = "timeout"


class LlmUnavailableError(RepositoryError):
    """The configured language model could not be reached, or refused the credentials.

    A subclass of RepositoryError because it is the same shape of failure: an outside
    system the request depends on is down, the caller did nothing wrong, and retrying
    later is the right advice. Callers that have a deterministic fallback catch this
    one specifically rather than every 503.
    """

    code = "llm_unavailable"


class RateLimitedError(AppError):
    """The caller has spent their allowance for a metered operation."""

    status_code = 429
    code = "rate_limited"
