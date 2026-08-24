"""Integration fixtures: live local Postgres, real app, one session-scoped client.

Environment defaults are set *before* anything from ``backend`` is imported so the cached
settings objects see them. ``setdefault`` yields to an exported shell value, which is why
the loopback guard below exists: this suite TRUNCATEs every table before every test.
"""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

os.environ.setdefault("APP_ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/cdtm_community_test")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes")
os.environ.setdefault("AUTH_ALLOWED_EMAIL_DOMAINS", "cdtm.com")
os.environ.setdefault("AUTH_ADMIN_EMAILS", "admin@cdtm.com")
os.environ.setdefault("AUTH_DEV_LOGIN_ENABLED", "true")
# Media lands in a scratch directory, never in the repository's .data/.
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_LOCAL_DIR", tempfile.mkdtemp(prefix="cdtm-media-"))
# Assigned, not setdefault: the repository .env may hold a real key, and no test is
# allowed to reach a provider or spend a token. Ask answers with keywords here.
os.environ["LLM_PROVIDER"] = "none"

import infrastructure.models  # noqa: E402,F401 - register all mappers
from backend.core.app import create_app  # noqa: E402
from backend.core.settings import get_database_settings, reset_settings_caches  # noqa: E402
from infrastructure.db import Base, get_sync_engine  # noqa: E402

pytestmark = pytest.mark.integration

LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_TRUNCATE_ADVISORY_LOCK_ID = 73450124


def require_local_database(engine: Engine) -> None:
    """Refuse to wipe anything that is not loopback. Fails closed on a host-less URL."""
    host = engine.url.host
    normalized = (host or "").strip().strip("[]").casefold()
    if normalized in LOCAL_DATABASE_HOSTS:
        return
    target = engine.url.render_as_string(hide_password=True)
    raise RuntimeError(
        f"Refusing to wipe the database at {target}: only loopback hosts are allowed. "
        "Unset DATABASE_URL (a Supabase env export is the usual culprit) and re-run."
    )


_engine = get_sync_engine()
require_local_database(_engine)


def _truncate_database() -> None:
    require_local_database(_engine)
    names = [
        _engine.dialect.identifier_preparer.quote(t.name)
        for t in reversed(Base.metadata.sorted_tables)
    ]
    for attempt in range(8):
        try:
            with _engine.begin() as conn:
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(:id)"), {"id": _TRUNCATE_ADVISORY_LOCK_ID}
                )
                if names:
                    conn.execute(
                        text(f"TRUNCATE TABLE {', '.join(names)} RESTART IDENTITY CASCADE")
                    )
            return
        except OperationalError as exc:
            if "deadlock" not in str(exc).lower() or attempt == 7:
                raise
            time.sleep(0.1 * (attempt + 1))


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    ini = os.path.join(os.path.dirname(__file__), "../../infrastructure/alembic.ini")
    command.upgrade(Config(ini), "head")


@pytest.fixture(scope="session")
def client() -> TestClient:
    """One TestClient (one event loop) for the whole session; asyncpg pools are loop-bound."""
    _migrate()
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolated_state(client: TestClient):
    reset_settings_caches()
    _truncate_database()
    yield


# ---- auth helpers -------------------------------------------------------------------------


def mint_token(
    email: str,
    *,
    sub: uuid.UUID | None = None,
    name: str | None = None,
    email_verified: bool = True,
) -> str:
    """An HS256 Supabase-shaped access token signed with the test secret.

    ``email_verified`` defaults to ``True``: every fixture and helper here (``auth()``,
    ``member_anna``, ``admin_headers``, ...) stands in for a real, completed Google sign-in,
    and the verifier now refuses to bind or allow-list an unverified address. Tests that
    specifically need an unverified token craft one directly rather than through this
    helper, so that attack stays visible at the call site.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": str(sub or uuid.uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        # Top level, where Supabase Auth writes it and where the verifier reads it.
        "email_verified": email_verified,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": {
            "email": email,
            "full_name": name or email.split("@")[0],
            "email_verified": True,
        },
        "app_metadata": {"provider": "google"},
    }
    return jwt.encode(payload, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")


def auth(email: str, **kw) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_token(email, **kw)}"}


def insert_member(slug: str, name: str, email: str | None = None, **cols) -> uuid.UUID:
    """Insert a bare member row directly; the loader is exercised by its own test."""
    member_id = uuid.uuid4()
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into members (id, slug, name, email, search_text, roles) "
                "values (:id, :slug, :name, :email, :st, '{}')"
            ),
            {"id": member_id, "slug": slug, "name": name, "email": email, "st": name.lower()},
        )
        for k, v in cols.items():
            # Column names come from the test body, never from input.
            conn.execute(
                text(f"update members set {k} = :v where id = :id"),  # noqa: S608
                {"v": v, "id": member_id},
            )
    return member_id


@pytest.fixture
def member_anna() -> dict:
    mid = insert_member("anna-test", "Anna Test", "anna.test@cdtm.com")
    return {
        "id": mid,
        "slug": "anna-test",
        "email": "anna.test@cdtm.com",
        "headers": auth("anna.test@cdtm.com"),
    }


@pytest.fixture
def member_ben() -> dict:
    mid = insert_member("ben-test", "Ben Test", "ben.test@cdtm.com")
    return {
        "id": mid,
        "slug": "ben-test",
        "email": "ben.test@cdtm.com",
        "headers": auth("ben.test@cdtm.com"),
    }


@pytest.fixture
def admin_headers() -> dict[str, str]:
    insert_member("admin-test", "Admin Test", "admin@cdtm.com")
    return auth("admin@cdtm.com")


@pytest.fixture
def db_settings():
    return get_database_settings()
