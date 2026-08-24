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


async def post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """POST ``payload``, retry once on 5xx, and return the decoded response body.

    A shared client is not kept: the app factory owns no lifespan hook this module could
    hang one off, and ask traffic is one request per question, so a per-call client costs
    a TCP handshake on a path that is already dominated by model latency.
    """
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout_s, transport=transport) as client:
        for attempt in range(_RETRIES + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)
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
