"""The two HTTP adapters, against a mock transport. No network, no credentials."""

import json

import httpx
import pytest

from backend.core.exceptions import LlmUnavailableError, ValidationError
from backend.core.llm import AnthropicCompleter, OpenAiCompatibleCompleter, get_structured_completer
from backend.core.settings import reset_settings_caches
from backend.core.settings.llm import LlmSettings

SCHEMA = {"type": "object", "properties": {"school": {"type": "string"}}}
ANSWER = {"school": "Stanford"}


@pytest.fixture(autouse=True)
def _clean_settings():
    reset_settings_caches()
    yield
    reset_settings_caches()


def _openai_response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["name"] == "member_query"
    assert request.headers["authorization"] == "Bearer key-1"
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ANSWER)}}]})


async def test_openai_parses_the_json_schema_answer() -> None:
    completer = OpenAiCompatibleCompleter(
        api_key="key-1",
        model="gpt-test",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(_openai_response),
    )
    assert (
        await completer.complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="member_query"
        )
        == ANSWER
    )


async def test_openai_refusal_is_a_422() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"refusal": "no"}}]})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ValidationError):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


async def test_anthropic_parses_the_forced_tool_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["x-api-key"] == "key-2"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert body["tool_choice"] == {"type": "tool", "name": "member_query"}
        assert body["tools"][0]["input_schema"] == SCHEMA
        assert str(request.url).endswith("/v1/messages")
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "here you go"},
                    {"type": "tool_use", "name": "member_query", "input": ANSWER},
                ]
            },
        )

    completer = AnthropicCompleter(
        api_key="key-2",
        model="claude-test",
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )
    assert (
        await completer.complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="member_query"
        )
        == ANSWER
    )


async def test_anthropic_without_a_tool_call_is_a_422() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "no thanks"}]})

    completer = AnthropicCompleter(api_key="k", model="m", transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


async def test_a_5xx_is_retried_once_and_then_reported_as_unavailable() -> None:
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503, json={"error": "down"})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailableError):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert len(attempts) == 2


async def test_a_5xx_followed_by_a_success_is_answered() -> None:
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(500, json={"error": "blip"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ANSWER)}}]})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    result = await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert result == ANSWER
    assert len(attempts) == 2


async def test_an_auth_failure_is_unavailable_not_a_500() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailableError):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


def _settings(**kw) -> LlmSettings:
    # _env_file=None: a developer's own .env must not decide what these tests assert.
    return LlmSettings(_env_file=None, **kw)


def test_no_provider_means_no_completer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.core.llm.get_llm_settings", lambda: _settings())
    assert get_structured_completer() is None


def test_a_provider_without_a_key_is_still_no_completer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.core.llm.get_llm_settings", lambda: _settings(provider="openai"))
    assert get_structured_completer() is None


def test_provider_defaults_fill_in_model_and_base_url() -> None:
    anthropic = _settings(provider="anthropic", api_key="k")
    assert anthropic.model == "claude-opus-5"
    assert anthropic.base_url == "https://api.anthropic.com"
    assert anthropic.configured is True

    openai = _settings(provider="openai", api_key="k")
    assert openai.model == "gpt-5.6-luna"
    assert openai.base_url == "https://api.openai.com/v1"

    gateway = _settings(provider="openai", api_key="k", model="llama-3", base_url="http://box/v1")
    assert (gateway.model, gateway.base_url) == ("llama-3", "http://box/v1")


def test_the_factory_picks_the_adapter_for_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core.llm.get_llm_settings", lambda: _settings(provider="anthropic", api_key="k")
    )
    assert isinstance(get_structured_completer(), AnthropicCompleter)
    monkeypatch.setattr(
        "backend.core.llm.get_llm_settings", lambda: _settings(provider="openai", api_key="k")
    )
    assert isinstance(get_structured_completer(), OpenAiCompatibleCompleter)


# ---- the exact wire contract -------------------------------------------------------------
#
# The provider answers with an error, not a correction, when a key is misspelled or a header
# is missing, and no test that only checks a couple of keys would notice. So these assert the
# whole outbound request: body, headers, URL and the timeout the client was configured with.

#: Set by httpx itself on every request; not part of what the adapters decide.
_TRANSPORT_HEADERS = frozenset(
    {"host", "accept", "accept-encoding", "connection", "user-agent", "content-length"}
)


def _sent(request: httpx.Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items() if k not in _TRANSPORT_HEADERS}


def _recorder(response: httpx.Response) -> tuple[list[httpx.Request], httpx.MockTransport]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response

    return seen, httpx.MockTransport(handler)


async def test_the_anthropic_request_is_exactly_the_documented_shape() -> None:
    seen, transport = _recorder(
        httpx.Response(
            200, json={"content": [{"type": "tool_use", "name": "member_query", "input": ANSWER}]}
        )
    )
    completer = AnthropicCompleter(
        api_key="key-2", model="claude-test", timeout_s=7.5, transport=transport
    )
    assert completer.model == "claude-test"
    await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="member_query")

    request = seen[0]
    # No base_url given: the default is the public API, and the path is /v1/messages.
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert json.loads(request.content) == {
        "model": "claude-test",
        # The default token budget, which is what an unconfigured deployment sends.
        "max_tokens": 1024,
        "system": "s",
        "messages": [{"role": "user", "content": "u"}],
        "tools": [
            {
                "name": "member_query",
                "description": "Record the interpreted query. Call this exactly once.",
                "input_schema": SCHEMA,
            }
        ],
        "tool_choice": {"type": "tool", "name": "member_query"},
    }
    assert _sent(request) == {
        "x-api-key": "key-2",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    # The configured budget is what the client waits for, not httpx's own default.
    assert request.extensions["timeout"]["read"] == 7.5


async def test_the_openai_request_is_exactly_the_documented_shape() -> None:
    seen, transport = _recorder(
        httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ANSWER)}}]})
    )
    completer = OpenAiCompatibleCompleter(
        api_key="key-1", model="gpt-test", timeout_s=7.5, transport=transport
    )
    assert completer.model == "gpt-test"
    await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="member_query")

    request = seen[0]
    assert str(request.url) == "https://api.openai.com/v1/chat/completions"
    assert json.loads(request.content) == {
        "model": "gpt-test",
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "member_query", "schema": SCHEMA, "strict": True},
        },
    }
    assert _sent(request) == {
        "authorization": "Bearer key-1",
        "content-type": "application/json",
    }
    assert request.extensions["timeout"]["read"] == 7.5


async def test_a_gateway_base_url_keeps_its_path_and_loses_its_trailing_slash() -> None:
    seen, transport = _recorder(
        httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ANSWER)}}]})
    )
    completer = OpenAiCompatibleCompleter(
        api_key="k", model="llama-3", base_url="http://box:8000/v1/", transport=transport
    )
    await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert str(seen[0].url) == "http://box:8000/v1/chat/completions"


async def test_the_default_timeout_is_the_documented_twenty_seconds() -> None:
    seen, transport = _recorder(
        httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ANSWER)}}]})
    )
    completer = OpenAiCompatibleCompleter(api_key="k", model="m", transport=transport)
    await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert seen[0].extensions["timeout"]["read"] == 20.0


# ---- reading the answer ------------------------------------------------------------------


async def test_anthropic_finds_the_tool_call_behind_a_text_block() -> None:
    """The model may narrate before it calls the tool, and the narration can carry the
    tool's name; only a ``tool_use`` block is an answer."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [
                    "a string, not a block",
                    {"type": "text", "name": "member_query", "text": "let me look"},
                    {"type": "tool_use", "name": "another_tool", "input": {"school": "wrong"}},
                    {"type": "tool_use", "name": "member_query", "input": ANSWER},
                ]
            },
        )

    completer = AnthropicCompleter(api_key="k", model="m", transport=httpx.MockTransport(handler))
    assert (
        await completer.complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="member_query"
        )
        == ANSWER
    )


async def test_anthropic_reports_a_tool_call_with_no_arguments() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"content": [{"type": "tool_use", "name": "n", "input": "not an object"}]}
        )

    completer = AnthropicCompleter(api_key="k", model="m", transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError, match="malformed tool call"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


async def test_anthropic_reports_an_answer_with_no_tool_call_at_all() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []})

    completer = AnthropicCompleter(api_key="k", model="m", transport=httpx.MockTransport(handler))
    with pytest.raises(ValidationError, match="did not call the requested tool"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


def _openai_completer(payload: dict) -> OpenAiCompatibleCompleter:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return OpenAiCompatibleCompleter(api_key="k", model="m", transport=httpx.MockTransport(handler))


async def test_openai_distinguishes_a_refusal_from_an_empty_answer() -> None:
    # Both are 422s, but only one of them is the model declining, and the difference is
    # what the log line and the fallback decision are read from.
    completer = _openai_completer({"choices": [{"message": {"refusal": "I cannot help"}}]})
    with pytest.raises(ValidationError, match="declined"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


async def test_openai_reports_an_empty_string_answer() -> None:
    completer = _openai_completer({"choices": [{"message": {"content": "   "}}]})
    with pytest.raises(ValidationError, match="empty answer"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")

    completer = _openai_completer({"choices": [{"message": {}}]})
    with pytest.raises(ValidationError, match="empty answer"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


async def test_openai_reports_an_answer_with_no_choices() -> None:
    completer = _openai_completer({"choices": []})
    with pytest.raises(ValidationError, match="no answer"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


async def test_openai_reports_content_that_is_not_a_json_object() -> None:
    completer = _openai_completer({"choices": [{"message": {"content": "not json at all"}}]})
    with pytest.raises(ValidationError, match="malformed JSON"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")

    completer = _openai_completer({"choices": [{"message": {"content": "[1, 2]"}}]})
    with pytest.raises(ValidationError, match="other than an object"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")


# ---- the transport itself ----------------------------------------------------------------


async def test_a_4xx_is_never_read_as_an_answer() -> None:
    """A provider that rejects the request still sends a JSON body; returning it would hand
    the caller a filter object made of an error payload."""
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailableError):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    # A rejected request is not retried: it would be rejected again.
    assert len(attempts) == 1


async def test_a_rate_limited_key_is_reported_as_such_and_not_retried() -> None:
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, json={"error": "slow down"})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailableError, match="rate limiting"):
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert len(attempts) == 1


async def test_a_connection_failure_is_retried_once_and_then_reported() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ConnectError("no route to host", request=request)

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailableError) as caught:
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert len(attempts) == 2
    # The transport failure is kept as the cause, which is what the traceback is read from.
    assert isinstance(caught.value.__cause__, httpx.HTTPError)


async def test_a_persistent_5xx_keeps_the_response_that_caused_it() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    completer = OpenAiCompatibleCompleter(
        api_key="k", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailableError) as caught:
        await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    cause = caught.value.__cause__
    assert isinstance(cause, httpx.HTTPStatusError)
    assert cause.response.status_code == 503
    assert cause.request is not None


async def test_the_anthropic_default_timeout_is_the_documented_twenty_seconds() -> None:
    seen, transport = _recorder(
        httpx.Response(200, json={"content": [{"type": "tool_use", "name": "n", "input": ANSWER}]})
    )
    completer = AnthropicCompleter(api_key="k", model="m", transport=transport)
    await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert seen[0].extensions["timeout"]["read"] == 20.0


async def test_an_anthropic_gateway_url_loses_its_trailing_slash() -> None:
    seen, transport = _recorder(
        httpx.Response(200, json={"content": [{"type": "tool_use", "name": "n", "input": ANSWER}]})
    )
    completer = AnthropicCompleter(
        api_key="k",
        model="m",
        base_url="https://proxy.example.test/anthropic/",
        transport=transport,
    )
    await completer.complete_json(system="s", user="u", schema=SCHEMA, schema_name="n")
    assert str(seen[0].url) == "https://proxy.example.test/anthropic/v1/messages"
