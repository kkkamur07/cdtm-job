"""Language model access, as one narrow port and two HTTP adapters.

Nothing here knows what a Member or a Job is. A caller hands over a system prompt, a
question and a JSON schema, and gets back a dict. The model never sees community data and
never reaches the database.
"""

from __future__ import annotations

from backend.core.llm._http import aclose_shared_client
from backend.core.llm.anthropic import AnthropicCompleter
from backend.core.llm.openai_compatible import OpenAiCompatibleCompleter
from backend.core.llm.ports import StructuredCompleter
from backend.core.llm.schema import strict_json_schema
from backend.core.settings import get_llm_settings

__all__ = [
    "AnthropicCompleter",
    "OpenAiCompatibleCompleter",
    "StructuredCompleter",
    "aclose_shared_client",
    "get_structured_completer",
    "strict_json_schema",
]


def get_structured_completer() -> StructuredCompleter | None:
    """The configured adapter, or ``None`` when no provider is set up.

    ``None`` is not an error state. Every caller has a deterministic fallback, so an
    install with no credentials still answers questions, just less cleverly.
    """
    s = get_llm_settings()
    if not s.configured or s.api_key is None:
        return None
    if s.provider == "anthropic":
        return AnthropicCompleter(
            api_key=s.api_key, model=s.model, base_url=s.base_url, timeout_s=s.timeout_s
        )
    return OpenAiCompatibleCompleter(
        api_key=s.api_key, model=s.model, base_url=s.base_url, timeout_s=s.timeout_s
    )
