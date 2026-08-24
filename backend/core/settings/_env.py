from __future__ import annotations

from pathlib import Path

from pydantic_settings import SettingsConfigDict

CORE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CORE_DIR.parent.parent
#: The repository-root ``.env`` is the env file every settings class reads (it is gitignored;
#: ``.env.example`` next to it is the template). ``backend/core/.env`` is honoured as a second
#: file for people who keep backend settings with the backend.
ENV_FILES = (REPO_ROOT / ".env", CORE_DIR / ".env")


def env_settings_config(prefix: str = "") -> SettingsConfigDict:
    """Shared ``model_config`` for every settings class.

    Process environment wins over the files. ``env_ignore_empty=True`` because a template
    line such as ``SUPABASE_JWT_SECRET=`` must mean "unset", not "the empty string"; the
    empty string would otherwise validate and the API would accept no token at all.
    """
    return SettingsConfigDict(
        env_file=[str(p) for p in ENV_FILES],
        env_file_encoding="utf-8",
        env_prefix=prefix,
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )
