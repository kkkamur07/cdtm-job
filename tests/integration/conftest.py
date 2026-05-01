"""Live Supabase fixtures — loads repo-root ``.env`` and uses real ``Settings``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.api.deps import get_settings
from backend.api.main import create_app
from backend.core.supabase_client import _client_cache

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _clear_backend_caches() -> None:
    get_settings.cache_clear()
    _client_cache.cache_clear()


def live_supabase_configured() -> bool:
    """Return True if live credentials look configured."""
    load_dotenv(_REPO_ROOT / ".env")
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
            "(repo-root .env or exported env).",
        )
    _clear_backend_caches()

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def api_prefix() -> str:
    _clear_backend_caches()
    load_dotenv(_REPO_ROOT / ".env")
    if not live_supabase_configured():
        pytest.skip("No live Supabase configuration.")
    return get_settings().api_route_prefix
