from pathlib import Path

import pytest

from backend.core.settings import reset_settings_caches
from backend.core.settings._cache import settings_cache
from backend.core.settings._env import env_settings_config
from backend.core.settings.database import DatabaseSettings
from backend.core.settings.storage import StorageSettings


def test_database_urls_are_normalised_per_driver() -> None:
    s = DatabaseSettings(url="postgres://u:p@db.example.com:6543/app")
    assert s.async_url == "postgresql+asyncpg://u:p@db.example.com:6543/app"
    assert s.sync_url == "postgresql+psycopg://u:p@db.example.com:6543/app"
    assert s.migrator_url == s.sync_url


def test_migrator_url_override_wins() -> None:
    s = DatabaseSettings(
        url="postgresql://u:p@pooler:6543/app",
        DATABASE_MIGRATOR_URL="postgresql://u:p@direct:5432/app",
    )
    assert s.migrator_url == "postgresql+psycopg://u:p@direct:5432/app"


def test_an_already_qualified_url_is_renormalised_to_the_driver_that_is_asked_for() -> None:
    """A DATABASE_URL copied out of another tool's config already names a driver. Whichever
    one it names, each caller still gets the driver it needs: asyncpg for the API, psycopg
    for Alembic."""
    for url in (
        "postgresql+asyncpg://u:p@h:5432/db",
        "postgresql+psycopg://u:p@h:5432/db",
        "postgresql+psycopg2://u:p@h:5432/db",
    ):
        s = DatabaseSettings(url=url)
        assert s.async_url == "postgresql+asyncpg://u:p@h:5432/db"
        assert s.sync_url == "postgresql+psycopg://u:p@h:5432/db"


def test_a_url_for_another_store_is_left_alone() -> None:
    # Nothing here knows how to rewrite it, and quietly prefixing it would produce a URL
    # that fails much later with a much stranger message.
    s = DatabaseSettings(url="sqlite+aiosqlite:///./local.db")
    assert s.async_url == "sqlite+aiosqlite:///./local.db"


def test_the_avatar_url_is_built_from_the_project_url_and_the_bucket() -> None:
    s = StorageSettings(_env_file=None, SUPABASE_URL="https://proj.supabase.co/")
    # One slash between every segment, whatever the configured URL and the stored path
    # happen to end and start with.
    assert (
        s.public_url("/anna.webp")
        == "https://proj.supabase.co/storage/v1/object/public/avatars/anna.webp"
    )
    assert (
        s.public_url("nested/anna.webp")
        == "https://proj.supabase.co/storage/v1/object/public/avatars/nested/anna.webp"
    )


def test_there_is_no_public_avatar_url_without_a_project() -> None:
    # A local-disk deployment has no Supabase project to serve one from.
    assert StorageSettings(_env_file=None).public_url("anna.webp") is None


def test_an_empty_environment_value_means_unset_not_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # A template line such as `DATABASE_URL=` must not resolve to the empty string; the
    # same rule is what stops an empty SUPABASE_JWT_SECRET validating and disabling auth.
    monkeypatch.setenv("DATABASE_URL", "")
    assert DatabaseSettings(_env_file=None).url == "postgresql://localhost:5432/cdtm_community"


def test_the_environment_is_read_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("database_url", "postgresql://lower:5432/db")
    assert DatabaseSettings(_env_file=None).url == "postgresql://lower:5432/db"


def test_only_prefixed_variables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    # Without the prefix a bare POOL_SIZE in the environment would silently reconfigure the
    # connection pool.
    monkeypatch.setenv("POOL_SIZE", "99")
    assert DatabaseSettings(_env_file=None).pool_size == 5
    monkeypatch.setenv("DATABASE_POOL_SIZE", "7")
    assert DatabaseSettings(_env_file=None).pool_size == 7


def test_an_unknown_prefixed_variable_does_not_stop_the_process_booting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_SOMETHING_ELSE", "x")
    assert DatabaseSettings(_env_file=None).pool_size == 5


def test_the_shared_config_reads_the_repository_env_file() -> None:
    config = env_settings_config("DATABASE_")
    assert [Path(p).name for p in config["env_file"]] == [".env", ".env"]
    assert config["env_file_encoding"] == "utf-8"
    assert config["env_prefix"] == "DATABASE_"
    assert config["env_ignore_empty"] is True
    assert config["extra"] == "ignore"
    assert config["case_sensitive"] is False
    # Unprefixed by default, for the classes that read SUPABASE_* and friends directly.
    assert env_settings_config()["env_prefix"] == ""


def test_a_settings_object_is_resolved_once_and_released_by_the_reset() -> None:
    """Every settings accessor is cached so a request never re-reads the environment, and
    every cache is registered so the test suite can hand each test a clean one."""
    resolutions: list[int] = []

    @settings_cache
    def _resolve() -> object:
        resolutions.append(1)
        return object()

    first = _resolve()
    assert _resolve() is first
    assert len(resolutions) == 1

    reset_settings_caches()
    second = _resolve()
    assert second is not first
    assert len(resolutions) == 2
