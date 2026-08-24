"""The development login against the real app: it must end in the same state a real one does."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.core.settings import reset_settings_caches
from tests.integration.conftest import _engine, insert_member

pytestmark = pytest.mark.integration

LOGIN = "/api/v1/auth/dev/login"


def _member_email(slug: str) -> str | None:
    with _engine.begin() as conn:
        return conn.scalar(text("select email from members where slug = :s"), {"s": slug})


def test_login_creates_an_account_and_the_token_works(client: TestClient) -> None:
    r = client.post(LOGIN, json={"email": "New.Person@cdtm.com"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 12 * 60 * 60
    assert body["me"]["account"]["email"] == "new.person@cdtm.com"
    assert body["me"]["member_id"] is None

    # The minted token goes through the ordinary verifier on the ordinary route.
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["account"]["id"] == body["me"]["account"]["id"]


def test_repeated_login_reuses_the_same_account(client: TestClient) -> None:
    first = client.post(LOGIN, json={"email": "stable@cdtm.com"}).json()
    second = client.post(LOGIN, json={"email": "stable@cdtm.com"}).json()
    assert first["me"]["account"]["id"] == second["me"]["account"]["id"]


def test_login_binds_to_a_member_that_already_has_the_email(
    client: TestClient, member_anna: dict
) -> None:
    body = client.post(
        LOGIN, json={"email": member_anna["email"], "member_slug": "anna-test"}
    ).json()
    assert body["me"]["member_slug"] == "anna-test"
    assert body["me"]["member_id"] == str(member_anna["id"])


def test_member_slug_claims_a_member_without_an_email(client: TestClient) -> None:
    insert_member("no-email", "No Email")
    r = client.post(LOGIN, json={"email": "dev@cdtm.com", "member_slug": "no-email"})
    assert r.status_code == 200, r.text
    assert r.json()["me"]["member_slug"] == "no-email"
    assert _member_email("no-email") == "dev@cdtm.com"


def test_claiming_a_member_with_a_different_email_is_a_conflict(
    client: TestClient, member_anna: dict
) -> None:
    r = client.post(LOGIN, json={"email": "someone.else@cdtm.com", "member_slug": "anna-test"})
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "conflict"
    # The row is untouched.
    assert _member_email("anna-test") == member_anna["email"]


def test_unknown_member_slug_is_not_found(client: TestClient) -> None:
    r = client.post(LOGIN, json={"email": "dev@cdtm.com", "member_slug": "nobody"})
    assert r.status_code == 404


def test_foreign_domain_is_forbidden_and_writes_nothing(client: TestClient) -> None:
    insert_member("untouched", "Untouched")
    r = client.post(LOGIN, json={"email": "outsider@gmail.com", "member_slug": "untouched"})
    assert r.status_code == 403
    assert _member_email("untouched") is None


def test_admin_email_is_bootstrapped_like_a_real_login(client: TestClient) -> None:
    body = client.post(LOGIN, json={"email": "admin@cdtm.com"}).json()
    assert body["me"]["is_admin"] is True


def test_member_picker_searches_name_and_slug(client: TestClient) -> None:
    insert_member("anna-test", "Anna Test", "anna.test@cdtm.com")
    insert_member("ben-test", "Ben Test")

    # No auth header: the picker is what you use before you have a token.
    everyone = client.get("/api/v1/auth/dev/members")
    assert everyone.status_code == 200, everyone.text
    assert {m["slug"] for m in everyone.json()} == {"anna-test", "ben-test"}

    by_name = client.get("/api/v1/auth/dev/members", params={"q": "anna"}).json()
    assert [m["slug"] for m in by_name] == ["anna-test"]
    # The picker is unauthenticated, so it hands out the slug that POST /auth/dev/login
    # wants and never the Workspace address behind it.
    assert "email" not in by_name[0]

    by_slug = client.get("/api/v1/auth/dev/members", params={"q": "ben-t"}).json()
    assert [m["slug"] for m in by_slug] == ["ben-test"]


def test_routes_are_absent_when_the_flag_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.core.app import create_app

    monkeypatch.setenv("AUTH_DEV_LOGIN_ENABLED", "false")
    reset_settings_caches()
    # No lifespan: entering the TestClient context would dispose the engine the session
    # client shares. These two routes never reach the database anyway.
    app = create_app()
    disabled = TestClient(app)
    assert disabled.post(LOGIN, json={"email": "dev@cdtm.com"}).status_code == 404
    assert disabled.get("/api/v1/auth/dev/members").status_code == 404
    assert not [r for r in app.routes if "/auth/dev" in getattr(r, "path", "")]


def test_production_refuses_to_boot_with_dev_login_on(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.core.app import create_app

    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_DEV_LOGIN_ENABLED", "true")
    reset_settings_caches()
    with pytest.raises(RuntimeError, match="AUTH_DEV_LOGIN_ENABLED"):
        create_app()
