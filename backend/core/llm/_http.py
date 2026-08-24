"""Shared transport behaviour for the model adapters.

Both adapters speak plain HTTP with httpx rather than a vendor SDK: two endpoints, one
request shape each, and no dependency that has to be kept in step with a provider's
release cadence.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.core.exceptions import LlmUnavailableError, ValidationError

logger = logging.getLogger(__name__)

#: One retry, not three. A question is answered inside a request the member is waiting on,
#: so the worst case has to stay inside the 20 s budget rather than multiply it.
_RETRIES = 1

#: The process-wide client every real completion goes through, built on first use.
_shared: httpx.AsyncClient | None = None


def shared_client() -> httpx.AsyncClient:
    """The one client the adapters post through, so the TLS handshake happens once.

    This used to be a client per call, on the grounds that the app factory had no lifespan
    hook to hang a long-lived one off. It has one now (``backend/core/app.py``), and a new
    client per question means a fresh TCP connect plus a TLS handshake to the provider on
    every Ask: a few hundred milliseconds of a budget the member is waiting on, spent on
    nothing. The connection pool inside the client keeps the socket between questions.

    No timeout is set here. It belongs to the call, not to the client, because each adapter
    is configured with its own ``LLM_TIMEOUT_S``; :func:`post_json` passes it per request.
    """
    global _shared
    if _shared is None:
        _shared = httpx.AsyncClient()
    return _shared


async def aclose_shared_client() -> None:
    """Close the shared client and forget it, on application shutdown.

    Forgetting it matters as much as closing it: the pool inside a client belongs to the
    event loop that opened the sockets, so a second app in the same process (the test suite
    builds several) has to get a client of its own rather than one holding dead connections.
    """
    global _shared
    client, _shared = _shared, None
    if client is not None:
        await client.aclose()


async def post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """POST ``payload``, retry once on 5xx, and return the decoded response body.

    The shared client above carries the connection pool. A caller that supplies its own
    ``transport`` (the tests, which answer without a network) gets a throwaway client
    instead, because a transport is a property of a client and swapping one into the shared
    pool would leak a stub into whatever ran next.
    """
    if transport is not None:
        async with httpx.AsyncClient(timeout=timeout_s, transport=transport) as client:
            return await _post(client, url=url, headers=headers, payload=payload, timeout_s=None)
    return await _post(
        shared_client(), url=url, headers=headers, payload=payload, timeout_s=timeout_s
    )


async def _post(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float | None,
) -> dict[str, Any]:
    """The request, the one retry and the status handling, given a client to use."""
    last_error: Exception | None = None
    for attempt in range(_RETRIES + 1):
        try:
            if timeout_s is None:
                response = await client.post(url, headers=headers, json=payload)
            else:
                response = await client.post(url, headers=headers, json=payload, timeout=timeout_s)
        except httpx.HTTPError as exc:
            # Connect errors and timeouts are worth one retry for the same reason 5xx is.
            last_error = exc
            if attempt < _RETRIES:
                continue
            raise LlmUnavailableError("the language model did not answer in time") from exc

        if response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                f"{response.status_code}", request=response.request, response=response
            )
            if attempt < _RETRIES:
                continue
            raise LlmUnavailableError(
                "the language model is temporarily unavailable"
            ) from last_error
        if response.status_code == 429:
            raise LlmUnavailableError("the language model is rate limiting this key")
        if response.status_code >= 400:
            logger.warning(
                "llm_request_rejected status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise LlmUnavailableError("the language model rejected the request")
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ValidationError("the language model answered with malformed JSON") from exc
    raise LlmUnavailableError("the language model is unavailable")  # pragma: no cover


def parse_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("the language model answered with malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise ValidationError("the language model answered with something other than an object")
    return parsed
