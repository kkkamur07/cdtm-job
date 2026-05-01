"""Application settings loaded from the process environment.

**Local development**

- Copy ``.env.example`` to ``.env`` at the **repository root** (next to
  ``pyproject.toml``). That path is what ``_env_file_for_config()`` resolves to by
  default (``backend`` → parents → repo root, then ``.env``).
- Or set ``BACKEND_ENV_FILE`` to an absolute path to a dotenv file you keep
  elsewhere.

**What loads ``.env``**

- ``pydantic_settings.BaseSettings`` with ``SettingsConfigDict(env_file=...)``.
  When ``env_file`` is a path to an existing file, pydantic-settings parses it
  using **python-dotenv** (installed transitively with ``pydantic-settings``):
  standard ``KEY=value`` lines, ``#`` comments, etc.
- **Precedence:** values already present in the **process environment** (shell
  exports, ``docker run -e``, platform secrets) **override** the same keys from
  the dotenv file.

**Production**

- Often there is **no** dotenv file in the image; ``env_file`` becomes ``None``
  and every variable comes from injected OS env only — same ``Settings`` class.
"""

from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor for default dotenv path (dev). Not required in prod when env vars are injected.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_file_for_config() -> str | None:
    """Return the dotenv path for ``SettingsConfigDict(env_file=...)`` or ``None``.

    If ``None``, pydantic-settings does not read a file; local overrides still work
    via exported env vars. If a path is returned and the file exists, that file is
    loaded for local dev (see module docstring).
    """
    raw = os.environ.get("BACKEND_ENV_FILE")
    path = Path(raw).expanduser().resolve() if raw else _REPO_ROOT / ".env"
    return str(path) if path.is_file() else None


class Settings(BaseSettings):
    """Base settings; validates and normalizes env-backed configuration."""

    model_config = SettingsConfigDict(
        # Dotenv path from _env_file_for_config(); parsed by pydantic-settings + python-dotenv.
        env_file=_env_file_for_config(),
        env_file_encoding="utf-8",
        extra="ignore",
        str_strip_whitespace=True,
    )

    supabase_url: HttpUrl
    supabase_service_role_key: SecretStr
    supabase_anon_key: SecretStr | None = None

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)

    cors_origins: str = "http://localhost:3000"

    #: Base path for versioned REST routes (e.g. ``/api/v1``, ``/api/v2``). Env: ``API_ROUTE_PREFIX``.
    api_route_prefix: str = Field(default="/api/v1")

    app_env: Literal["local", "staging", "production"] = "local"

    supabase_access_token: str | None = None
    supabase_project_ref: str | None = None

    @field_validator("supabase_url", mode="before")
    @classmethod
    def _ensure_https_supabase(cls, v: object) -> object:
        if isinstance(v, str) and v.startswith("http://"):
            lower = v.lower()
            if "localhost" not in lower and "127.0.0.1" not in lower:
                msg = "SUPABASE_URL must use https except for localhost / 127.0.0.1"
                raise ValueError(msg)
        return v

    @field_validator("cors_origins")
    @classmethod
    def _normalize_cors_string(cls, v: str) -> str:
        return v.strip()

    @field_validator("api_route_prefix")
    @classmethod
    def _normalize_api_route_prefix(cls, v: str) -> str:
        s = v.strip().rstrip("/")
        if not s.startswith("/"):
            s = "/" + s
        return s or "/api/v1"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        parts = [p.strip() for p in self.cors_origins.split(",")]
        return [p for p in parts if p]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _validate_production_cors(self) -> Settings:
        if self.app_env == "production":
            origins = [p.strip() for p in self.cors_origins.split(",") if p.strip()]
            if any(o == "*" for o in origins):
                msg = "Wildcard CORS origins are not allowed when APP_ENV=production"
                raise ValueError(msg)
        return self

    @cached_property
    def repo_root(self) -> Path:
        return _REPO_ROOT
