import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import auth

pytestmark = pytest.mark.integration


def _raw_token(**payload_overrides) -> str:
    """A hand-crafted Supabase-shaped token, bypassing ``mint_token`` so a test can control
    exactly which claims are present (or absent) at the top level."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": {},
        "app_metadata": {"provider": "google"},
    }
    payload.update(payload_overrides)
    return jwt.encode(payload, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")


def test_me_binds_account_to_member_by_email(client: TestClient, member_anna: dict) -> None:
    r = client.get("/api/v1/auth/me", headers=member_anna["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["member_slug"] == "anna-test"
    assert body["account"]["email"] == "anna.test@cdtm.com"
    assert body["is_admin"] is False


def test_foreign_domain_is_forbidden(client: TestClient) -> None:
    r = client.get("/api/v1/auth/me", headers=auth("stranger@gmail.com"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_garbage_token_is_unauthorized(client: TestClient) -> None:
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_metadata_only_email_is_rejected(client: TestClient) -> None:
    """Attack (11a): a token that carries an e-mail only inside ``user_metadata`` — a field
    the end user can edit through Supabase's own update-user call. Falling back to it would
    let anyone sign in as any Member whose mailbox they merely typed into their own profile.
    Only the top-level ``email`` claim, which Supabase Auth itself writes, may be trusted."""
    token = _raw_token(user_metadata={"email": "ghost@cdtm.com", "email_verified": True})
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 200, r.text


def test_unverified_top_level_email_is_rejected(client: TestClient) -> None:
    """Attack (11b): a token with a genuine top-level ``email`` claim but no proof Supabase
    ever verified it (``email_verified`` absent or false). An unverified address must not be
    trusted for account binding or the domain allow-list — otherwise anyone who can get a
    token minted with an arbitrary, unconfirmed ``email`` claim binds to any Member's roster
    row or passes the CDTM domain gate on a mailbox they do not own."""
    token = _raw_token(email="victim@cdtm.com")  # email_verified absent
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 200, r.text

    token = _raw_token(email="victim@cdtm.com", email_verified=False)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 200, r.text


def test_verified_top_level_email_still_works(client: TestClient) -> None:
    """The legitimate path must not be collateral damage of closing 11b."""
    token = _raw_token(email="verified.person@cdtm.com", email_verified=True)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["account"]["email"] == "verified.person@cdtm.com"


def test_admin_can_bind_unmatched_account(
    client: TestClient, admin_headers: dict, member_ben: dict
) -> None:
    # an account whose e-mail is not on any member
    r = client.get("/api/v1/auth/me", headers=auth("newbie@cdtm.com"))
    assert r.status_code == 200 and r.json()["member_id"] is None
    account_id = r.json()["account"]["id"]
    r = client.post(
        f"/api/v1/auth/accounts/{account_id}/bind",
        json={"member_slug": "ben-test"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["member_id"] == str(member_ben["id"])
    # non-admin cannot
    r = client.post(
        f"/api/v1/auth/accounts/{account_id}/bind",
        json={"member_slug": "ben-test"},
        headers=member_ben["headers"],
    )
    assert r.status_code == 403


def test_only_an_admin_can_grant_admin(
    client: TestClient, admin_headers: dict, member_ben: dict
) -> None:
    """Granting admin is an admin-only power, and the grant has to actually take.

    Guards ``AuthService.set_admin`` from both directions: a non-admin calling the endpoint
    is refused and the target stays unprivileged, and an admin's grant persists. An inverted
    gate (refuse admins, allow everyone else) would let any member promote anyone and is
    otherwise invisible: nothing else exercises this endpoint.
    """
    # One token per identity: re-minting would carry a fresh ``sub`` and 409 on the account.
    h_newbie = auth("newbie2@cdtm.com")
    r = client.get("/api/v1/auth/me", headers=h_newbie)
    assert r.status_code == 200, r.text
    account_id = r.json()["account"]["id"]
    assert r.json()["is_admin"] is False

    # A non-admin cannot promote anyone, and the target is untouched.
    assert (
        client.post(
            f"/api/v1/auth/accounts/{account_id}/admin",
            json={"is_admin": True},
            headers=member_ben["headers"],
        ).status_code
        == 403
    )
    assert client.get("/api/v1/auth/me", headers=h_newbie).json()["is_admin"] is False

    # An admin can, and the bit persists on the account.
    r = client.post(
        f"/api/v1/auth/accounts/{account_id}/admin",
        json={"is_admin": True},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_admin"] is True
    assert client.get("/api/v1/auth/me", headers=h_newbie).json()["is_admin"] is True


def test_admin_lists_accounts_and_can_ask_for_the_unbound_ones(
    client: TestClient, admin_headers: dict, member_ben: dict
) -> None:
    """The worklist behind the bind page: who has signed in and still has no Member."""
    # An account exists once its owner has presented a token, so sign both of them in.
    client.get("/api/v1/auth/me", headers=auth("newbie@cdtm.com"))
    client.get("/api/v1/auth/me", headers=member_ben["headers"])
    r = client.get("/api/v1/auth/accounts", headers=admin_headers)
    assert r.status_code == 200, r.text
    emails = {a["email"] for a in r.json()["items"]}
    assert {"newbie@cdtm.com", "ben.test@cdtm.com", "admin@cdtm.com"} <= emails
    fields = r.json()["items"][0]
    assert {"id", "email", "member_id", "is_admin", "created_at", "last_sign_in_at"} <= set(fields)

    r = client.get("/api/v1/auth/accounts", params={"unbound": True}, headers=admin_headers)
    unbound = r.json()["items"]
    assert [a["email"] for a in unbound if a["email"] == "ben.test@cdtm.com"] == []
    assert all(a["member_id"] is None for a in unbound)
    assert "newbie@cdtm.com" in {a["email"] for a in unbound}

    # Paging is the ordinary skip/limit: one item on the page, the full count alongside.
    page = client.get("/api/v1/auth/accounts", params={"limit": 1}, headers=admin_headers).json()
    assert len(page["items"]) == 1
    assert page["total"] >= 3

    assert client.get("/api/v1/auth/accounts", headers=member_ben["headers"]).status_code == 403
