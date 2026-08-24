"""Structured completion against any OpenAI-compatible ``/chat/completions`` endpoint.

Works with OpenAI itself and with the gateways that copy its wire format (Azure OpenAI,
OpenRouter, Together, vLLM, Ollama's OpenAI shim): point ``LLM_BASE_URL`` at the base and
name the model in ``LLM_MODEL``.
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.core.exceptions import ValidationError
from backend.core.llm._http import parse_json_object, post_json


class OpenAiCompatibleCompleter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def complete_json(
        self, *, system: str, user: str, schema: dict, schema_name: str
    ) -> dict:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # strict:true is what makes the answer parseable without repair: the provider
            # constrains decoding to the schema instead of asking the model to behave.
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
        }
        body = await post_json(
            url=f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout_s=self._timeout_s,
            transport=self._transport,
        )
        choices = body.get("choices") or []
        if not choices:
            raise ValidationError("the language model returned no answer")
        message = choices[0].get("message") or {}
        if message.get("refusal"):
            raise ValidationError("the language model declined to answer that question")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValidationError("the language model returned an empty answer")
        return parse_json_object(content)
