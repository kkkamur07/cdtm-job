import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> Path:
    """Resolve which `.env` file to load.

    You can skip implicit path resolution entirely by setting **BACKEND_ENV_FILE** to an
    absolute path (common in Docker / CI). Otherwise we load **repo-root** ``.env``:
    this file lives at ``backend/api/settings.py``, so three ``.parent`` hops reach the repo.
    """
    override = os.environ.get("BACKEND_ENV_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings from environment variables (and optional ``.env`` file)."""

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_service_role_key: str

    api_host: str = Field(default="0.0.0.0", description="Bind address for Uvicorn.")
    api_port: int = Field(default=8000, description="Bind port for Uvicorn.")

    cors_origins: str = Field(
        default="http://localhost:3000",
        description=(
            "Comma-separated browser origins allowed to call this API (CORS). "
            "In production, set to your real frontend origins (e.g. https://jobs.cdtm.com)."
        ),
    )

    app_env: str = Field(
        default="local",
        description=(
            "Deployment label: local | staging | production. "
            "Use for log fields, metrics labels, or toggling dummy/demo behaviour — "
            "not a security boundary (do not hide secrets behind this value)."
        ),
    )

    slack_webhook_url: str | None = Field(
        default=None,
        description="Slack Incoming Webhook URL (optional). When set, publishing a job posts once (idempotent).",
    )
    resend_api_key: str | None = Field(
        default=None,
        description="Resend API key (optional). Email automation is stubbed until wired.",
    )
    posthog_api_key: str | None = Field(
        default=None,
        description="PostHog project API key (optional). Analytics calls are stubbed until wired.",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()
