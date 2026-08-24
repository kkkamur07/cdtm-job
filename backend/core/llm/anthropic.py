"""Structured completion against the Anthropic Messages API.

The Messages API has no ``response_format``. The equivalent is a forced tool call: the
schema is handed over as a tool's ``input_schema`` and ``tool_choice`` names that tool, so
the only thing the model can produce is an argument object shaped like the schema.
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.core.exceptions import ValidationError
from backend.core.llm._http import post_json

#: Pinned rather than tracked: the Messages request shape is versioned by this header, and
#: a silent upgrade is exactly the kind of change that should break a test, not production.
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicCompleter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        timeout_s: float = 20.0,
        max_tokens: int = 1024,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def complete_json(
        self, *, system: str, user: str, schema: dict, schema_name: str
    ) -> dict:
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [
                {
                    "name": schema_name,
                    "description": "Record the interpreted query. Call this exactly once.",
                    "input_schema": schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": schema_name},
        }
        body = await post_json(
            url=f"{self._base_url}/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout_s=self._timeout_s,
            transport=self._transport,
        )
        for block in body.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != schema_name:
                continue
            arguments = block.get("input")
            if not isinstance(arguments, dict):
                raise ValidationError("the language model returned a malformed tool call")
            return arguments
        raise ValidationError("the language model did not call the requested tool")
