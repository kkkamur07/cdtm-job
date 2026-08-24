"""The boot-time guard on the development login."""

from __future__ import annotations

import pytest

from backend.core.app import _check_dev_login
from backend.core.settings import AppSettings, AuthSettings

SECRET = "unit-test-secret-at-least-32-bytes-long"


def test_dev_login_off_needs_nothing() -> None:
    # Every value is passed explicitly: the integration conftest exports
    # AUTH_DEV_LOGIN_ENABLED at import time and pytest imports it in both lanes.
    _check_dev_login(
        AppSettings(environment="production"),
        AuthSettings(dev_login_enabled=False, SUPABASE_JWT_SECRET=None),
    )


def test_dev_login_on_in_development_is_fine() -> None:
    _check_dev_login(
        AppSettings(environment="development"),
        AuthSettings(dev_login_enabled=True, SUPABASE_JWT_SECRET=SECRET),
    )


def test_dev_login_on_in_production_raises() -> None:
    with pytest.raises(RuntimeError, match="AUTH_DEV_LOGIN_ENABLED"):
        _check_dev_login(
            AppSettings(environment="production"),
            AuthSettings(dev_login_enabled=True, SUPABASE_JWT_SECRET=SECRET),
        )


def test_dev_login_without_a_signing_secret_raises() -> None:
    with pytest.raises(RuntimeError, match="SUPABASE_JWT_SECRET"):
        _check_dev_login(
            AppSettings(environment="development"),
            AuthSettings(dev_login_enabled=True, SUPABASE_JWT_SECRET=None),
        )
