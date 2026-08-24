from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from backend.core.settings._cache import settings_cache
from backend.core.settings._env import env_settings_config

Provider = Literal["none", "openai", "anthropic"]

#: Defaults per provider, applied when ``LLM_MODEL`` / ``LLM_BASE_URL`` are not set.
#: They are only defaults: any OpenAI-compatible gateway works by pointing
#: ``LLM_BASE_URL`` at it and naming whatever model that gateway serves.
_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"model": "gpt-5.6-luna", "base_url": "https://api.openai.com/v1"},
    "anthropic": {"model": "claude-opus-5", "base_url": "https://api.anthropic.com"},
}


class LlmSettings(BaseSettings):
    """Which language model translates a plain-words question into filters, if any.

    ``provider="none"`` is the default and is a supported production configuration, not a
    broken one: every Ask endpoint falls back to the deterministic keyword translator, so
    the feature works with no credentials and no spend.
    """

    model_config = env_settings_config("LLM_")

    provider: Provider = "none"
    api_key: str | None = None
    model: str = ""
    base_url: str = ""
    timeout_s: float = Field(default=20.0, gt=0)
    # One question is one model call, so this is also the per-member spend ceiling.
    max_questions_per_minute: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def _apply_provider_defaults(self) -> LlmSettings:
        defaults = _PROVIDER_DEFAULTS.get(self.provider, {})
        # object.__setattr__ is not needed (the model is mutable), but assigning through
        # the normal path would re-run validation and recurse.
        if not self.model:
            self.__dict__["model"] = defaults.get("model", "")
        if not self.base_url:
            self.__dict__["base_url"] = defaults.get("base_url", "")
        return self

    @property
    def configured(self) -> bool:
        return self.provider != "none" and bool(self.api_key)


@settings_cache
def get_llm_settings() -> LlmSettings:
    return LlmSettings()
