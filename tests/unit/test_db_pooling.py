"""Which connections are treated as transaction-pooled, and what follows from that.

Two things hang off this answer: whether asyncpg may keep prepared statements (it may not
when the physical connection is handed to somebody else between transactions), and whether
``statement_timeout`` has to be re-armed inside every transaction because the startup
parameter may not have been forwarded.

The rule used to be "the host string contains pooler.supabase.com", which is wrong for the
configuration this platform actually uses: Supabase publishes session mode on port 5432 of
that same host, where prepared statements are safe and giving them up costs query-plan reuse
on every statement the API issues.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import event

import infrastructure.db as db
from backend.core.settings import get_database_settings, reset_settings_caches

POOLER = "pooler.supabase.com"
DIRECT = "db.abcdefgh.supabase.co"


@pytest.fixture(autouse=True)
def _no_listener_left_behind() -> Iterator[None]:
    """The listener is attached to a class, so it outlives whatever attached it.

    Nothing here builds an engine: the engine cache is process-wide and shared with the
    integration suite's application, and dropping it out from under a running app would swap
    an asyncpg pool for one bound to a different event loop.
    """
    db._sync_statement_timeout_listener(enabled=False)
    yield
    db._sync_statement_timeout_listener(enabled=False)


@pytest.mark.parametrize(
    ("url", "pooled"),
    [
        (f"postgresql+asyncpg://u:p@{POOLER}:6543/postgres", True),
        # The case the old substring rule got wrong: Supavisor in session mode holds the
        # connection for the whole session, so prepared statements survive.
        (f"postgresql+asyncpg://u:p@{POOLER}:5432/postgres", False),
        (f"postgresql+asyncpg://u:p@{DIRECT}:5432/postgres", False),
        # No port at all is the default 5432, which is a direct connection.
        (f"postgresql+asyncpg://u:p@{DIRECT}/postgres", False),
        ("postgresql+asyncpg://localhost:5432/cdtm_community", False),
        # A password with a colon and an at-sign in it: parsed, not searched for ":6543".
        ("postgresql+asyncpg://u:p%3A6543%40x@direct:5432/postgres", False),
    ],
)
def test_only_the_transaction_pooling_port_counts_as_pooled(url: str, pooled: bool) -> None:
    assert db._is_transaction_pooled(url, override=False) is pooled


def test_the_override_forces_pooled_handling_for_a_url_that_does_not_say() -> None:
    """Something in front of the pooler, or a Supavisor on a port of its own, cannot be read
    off the URL. ``DATABASE_POOLER_TRANSACTION_MODE`` is how an operator says so."""
    assert db._is_transaction_pooled(f"postgresql+asyncpg://u:p@{DIRECT}:5432/db", override=True)


def test_a_url_nothing_can_parse_is_not_guessed_at() -> None:
    assert db._is_transaction_pooled("not a url at all", override=False) is False


def test_the_statement_cache_is_only_given_up_where_it_has_to_be(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression this whole change is about: the pooler host on the session-mode port
    was giving up prepared statements for a hazard that was not there.

    ``create_async_engine`` is stood in for rather than called: the real one is cached for
    the process and shared with the integration suite's running application.
    """
    captured: dict[str, object] = {}

    def fake_create_async_engine(url: str, **kwargs: object) -> str:
        captured.clear()
        captured.update(kwargs["connect_args"])  # type: ignore[arg-type]
        return url

    monkeypatch.setattr(db, "create_async_engine", fake_create_async_engine)

    for url, cache_disabled in (
        (f"postgresql://u:p@{POOLER}:5432/postgres", False),
        (f"postgresql://u:p@{POOLER}:6543/postgres", True),
    ):
        monkeypatch.setenv("DATABASE_URL", url)
        reset_settings_caches()
        db.get_async_engine.__wrapped__()
        assert ("statement_cache_size" in captured) is cache_disabled
        # The startup parameter is sent either way; under transaction pooling it may simply
        # not arrive, which is what the per-transaction SET LOCAL is there for.
        assert "statement_timeout" in captured["server_settings"]  # type: ignore[operator]

    reset_settings_caches()


def test_the_per_transaction_timeout_is_installed_only_for_transaction_pooling() -> None:
    """``SET LOCAL statement_timeout`` is a statement per transaction. It buys nothing in
    session mode, where the asyncpg startup parameter already holds, so it is not installed
    there; under transaction pooling the startup parameter may never have been forwarded."""
    listener = db._statement_timeout_per_transaction

    db._sync_statement_timeout_listener(enabled=True)
    assert event.contains(db._AppSession, "after_begin", listener) is True

    # Idempotent: asking twice must not queue the statement twice per transaction.
    db._sync_statement_timeout_listener(enabled=True)
    db._sync_statement_timeout_listener(enabled=False)
    assert event.contains(db._AppSession, "after_begin", listener) is False


def test_the_timeout_statement_is_scoped_to_the_transaction_and_not_the_connection() -> None:
    """``SET SESSION`` would outlive the transaction, and under transaction pooling the
    connection belongs to somebody else by then."""
    issued: list[str] = []

    class _Connection:
        def exec_driver_sql(self, statement: str) -> None:
            issued.append(statement)

    reset_settings_caches()
    db._statement_timeout_per_transaction(None, None, _Connection())  # type: ignore[arg-type]

    expected = int(get_database_settings().statement_timeout_ms)
    assert issued == [f"SET LOCAL statement_timeout = {expected}"]


def test_the_listener_is_never_attached_to_sessions_this_app_does_not_own() -> None:
    """Alembic and the one-off scripts build plain ``Session`` objects off the sync engine.
    A listener on ``Session`` itself would fire for those too."""
    from sqlalchemy.orm import Session

    assert db._AppSession is not Session
    assert issubclass(db._AppSession, Session)


def test_a_password_never_reaches_a_log_line() -> None:
    assert db.safe_url("postgresql://u:supersecret@host:5432/db") == (
        "postgresql://u:***@host:5432/db"
    )
    assert db.safe_url("not a url") == "<unparseable database url>"


def test_the_boot_line_says_the_migrator_is_falling_back_and_what_the_pool_costs(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two things a deployment cannot see any other way.

    An empty ``DATABASE_MIGRATOR_URL`` reads as unset, so Alembic quietly runs through the
    runtime URL: the line has to say so in words, not leave it to be inferred from two URLs
    that look alike. And the pool budget is what has to be multiplied by ``--workers`` before
    it is compared with the pooler's own connection limit.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@pooler:6543/app")
    monkeypatch.setenv("DATABASE_MIGRATOR_URL", "")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "5")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "5")
    reset_settings_caches()
    try:
        with caplog.at_level("INFO", logger="infrastructure.db"):
            db.log_resolved_urls()
    finally:
        reset_settings_caches()

    (line,) = [r.getMessage() for r in caplog.records]
    assert "migrator falls back to DATABASE_URL" in line
    assert "pool=5+5(max 10 per worker)" in line
    # The password is never in a log line, here as anywhere else.
    assert ":p@" not in line


def test_the_boot_line_names_the_override_when_there_is_one(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@pooler:6543/app")
    monkeypatch.setenv("DATABASE_MIGRATOR_URL", "postgresql://u:p@direct:5432/app")
    reset_settings_caches()
    try:
        with caplog.at_level("INFO", logger="infrastructure.db"):
            db.log_resolved_urls()
    finally:
        reset_settings_caches()

    (line,) = [r.getMessage() for r in caplog.records]
    assert "falls back" not in line
    assert "direct:5432" in line
