"""Live Supabase fixtures — loads ``backend/.env`` (same rules as ``Settings``)."""

from __future__ import annotations

import os

import pytest

from backend.core.settings import load_backend_dotenv_into_environ

# ``backend.api.main`` builds ``app`` at import time; prime env before those imports.
load_backend_dotenv_into_environ()

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.deps import get_settings  # noqa: E402
from backend.api.main import create_app  # noqa: E402
from backend.core.supabase_client import _client_cache  # noqa: E402


def _clear_backend_caches() -> None:
    get_settings.cache_clear()
    _client_cache.cache_clear()


def live_supabase_configured() -> bool:
    """Return True if live credentials look configured."""
    load_backend_dotenv_into_environ()
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return False
    if "YOUR_PROJECT_REF" in url or "your-service-role-key" in key.lower():
        return False
    return True


@pytest.fixture
def live_api_client():
    """HTTP client against an in-process app using **real** Supabase env."""
    if not live_supabase_configured():
        pytest.skip(
            "Live Supabase tests need SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "in backend/.env (or BACKEND_ENV_FILE / exported env).",
        )
    _clear_backend_caches()

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def api_prefix() -> str:
    _clear_backend_caches()
    load_backend_dotenv_into_environ()
    if not live_supabase_configured():
        pytest.skip("No live Supabase configuration.")
    return get_settings().api_route_prefix
