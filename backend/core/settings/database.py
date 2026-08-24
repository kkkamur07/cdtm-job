from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings

from backend.core.settings._cache import settings_cache
from backend.core.settings._env import env_settings_config

_ASYNC_DRIVER = "postgresql+asyncpg://"
_SYNC_DRIVER = "postgresql+psycopg://"


def _with_driver(url: str, driver: str) -> str:
    """Normalise any ``postgres[ql][+x]://`` URL to the requested SQLAlchemy driver."""
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        "postgresql://",
        "postgres://",
    ):
        if url.startswith(prefix):
            return driver + url[len(prefix) :]
    return url


class DatabaseSettings(BaseSettings):
    """Postgres connection settings.

    ``DATABASE_URL`` is the runtime connection (Supabase: the transaction pooler on
    6543 works; direct 5432 is best for a single long-lived API). ``DATABASE_MIGRATOR_URL``
    is used by Alembic and must be a direct (non-pooled) connection; it defaults to
    ``DATABASE_URL``.
    """

    model_config = env_settings_config("DATABASE_")

    url: str = Field(default="postgresql://localhost:5432/cdtm_community")
    migrator_url_override: str | None = Field(default=None, alias="DATABASE_MIGRATOR_URL")
    pool_size: int = 5
    max_overflow: int = 5
    statement_timeout_ms: int = 15_000
    echo: bool = False
    # Force transaction-mode handling on (no prepared statements, per-transaction
    # statement_timeout) for a URL whose port does not give it away: a proxy in front of the
    # pooler, or a Supavisor deployment on a port of its own. Off by default because the port
    # is the reliable signal on Supabase itself; see ``infrastructure.db``.
    pooler_transaction_mode: bool = False

    @property
    def async_url(self) -> str:
        return _with_driver(self.url, _ASYNC_DRIVER)

    @property
    def sync_url(self) -> str:
        return _with_driver(self.url, _SYNC_DRIVER)

    @property
    def migrator_url(self) -> str:
        return _with_driver(self.migrator_url_override or self.url, _SYNC_DRIVER)


@settings_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()
