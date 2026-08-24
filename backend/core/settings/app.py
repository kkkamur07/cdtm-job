from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

from backend.core.settings._cache import settings_cache
from backend.core.settings._env import env_settings_config


class AppSettings(BaseSettings):
    """Process-level settings: environment, CORS, API prefix."""

    model_config = env_settings_config("APP_")

    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    # NoDecode: env values are plain comma lists, not JSON; the validator below splits them.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    # Public base URL of the frontend, used when building links in responses.
    frontend_url: str = "http://localhost:3000"
    # Public base URL of *this* API. Media responses hand out absolute URLs that go back
    # through the API (private buckets are never addressed by the browser), so the value has
    # to be the origin the browser can reach, not whatever host uvicorn happens to bind.
    public_base_url: str = "http://localhost:8000"
    # Above this, a request is logged at INFO with its timing; below it, at DEBUG. Every
    # request is timed either way, so turning the logger down to DEBUG is how you see the
    # fast ones, and the default log level shows only the ones worth reading. 500 ms is
    # roughly "a member noticed": the p95 of the list endpoints sits an order below it.
    slow_request_ms: int = 500

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@settings_cache
def get_app_settings() -> AppSettings:
    return AppSettings()
