"""Identity behaviour the existing suite leaves unobserved: what a sign-in records on the
account, the admin worklist's order and paging, the sign-in that cannot bind, and the
development login driven by ``member_slug`` alone.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.core.settings import reset_settings_caches
from backend.identity.api.dev_router import MEMBER_PICKER_LIMIT
from tests.integration.conftest import _engine, auth, insert_member

pytestmark = pytest.mark.integration

LOGIN = "/api/v1/auth/dev/login"
ACCOUNTS = "/api/v1/auth/accounts"
ME = "/api/v1/auth/me"


def _token(
    email: str,
    *,
    sub: uuid.UUID,
    full_name: str | None = None,
    avatar_url: str | None = None,
) -> str:
    """A Supabase-shaped token whose display fields the caller controls.

    ``mint_token`` in conftest never carries an avatar, and the avatar is half of what a
    sign-in is supposed to record on the account.
    """
    now = datetime.now(UTC)
    metadata: dict[str, str] = {}
    if full_name is not None:
        metadata["full_name"] = full_name
    if avatar_url is not None:
        metadata["avatar_url"] = avatar_url
    payload = {
        "sub": str(sub),
        "aud": "authenticated",
        "email": email,
        "email_verified": True,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": metadata,
        "app_metadata": {"provider": "google"},
    }
    return jwt.encode(payload, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _member_email(slug: str) -> str | None:
    with _engine.begin() as conn:
        return conn.scalar(text("select email from members where slug = :s"), {"s": slug})


# ---- what a sign-in records on the account ------------------------------------------------


def test_a_sign_in_records_the_name_avatar_and_time_from_the_token(client: TestClient) -> None:
    """The account row is the platform's copy of who signed in: the admin worklist shows the
    name and the last sign-in, and the frontend shows the avatar. All three come off the
    verified token and nothing else asserts that any of them survive the trip."""
    sub = uuid.uuid4()
    first = client.get(
        ME,
        headers=_headers(
            _token(
                "display.person@cdtm.com",
                sub=sub,
                full_name="Display Person",
                avatar_url="https://cdn.example.com/first.png",
            )
        ),
    )
    assert first.status_code == 200, first.text
    account = first.json()["account"]
    assert account["full_name"] == "Display Person"
    assert account["avatar_url"] == "https://cdn.example.com/first.png"
    assert account["last_sign_in_at"] is not None
    first_seen = account["last_sign_in_at"]

    # The same Supabase user signing in again takes the update path, where the very same
    # three fields are written a second time.
    second = client.get(
        ME,
        headers=_headers(
            _token(
                "display.person@cdtm.com",
                sub=sub,
                full_name="Renamed Person",
                avatar_url="https://cdn.example.com/second.png",
            )
        ),
    )
    assert second.status_code == 200, second.text
    updated = second.json()["account"]
    assert updated["id"] == account["id"]
    assert updated["full_name"] == "Renamed Person"
    assert updated["avatar_url"] == "https://cdn.example.com/second.png"
    assert updated["last_sign_in_at"] is not None
    assert updated["last_sign_in_at"] >= first_seen


# ---- the admin worklist -------------------------------------------------------------------


def test_the_account_worklist_is_newest_first_and_pages_from_there(
    client: TestClient, admin_headers: dict
) -> None:
    """An admin binding accounts by hand works through the people who have just signed in and
    found nothing of their own, so the order is part of the contract, and so is being able to
    ask for the second page rather than the first one again."""
    assert client.get(ME, headers=admin_headers).status_code == 200
    signed_in_order = ["first@cdtm.com", "second@cdtm.com", "third@cdtm.com"]
    for email in signed_in_order:
        assert client.get(ME, headers=auth(email)).status_code == 200

    page = client.get(ACCOUNTS, headers=admin_headers).json()
    listed = [a["email"] for a in page["items"] if a["email"] in signed_in_order]
    assert listed == list(reversed(signed_in_order))
    assert page["total"] == 4

    # Skipping one lands on the second newest, not on the first one all over again.
    second_page = client.get(ACCOUNTS, params={"skip": 1, "limit": 1}, headers=admin_headers)
    assert [a["email"] for a in second_page.json()["items"]] == ["second@cdtm.com"]
    assert second_page.json()["total"] == 4


def test_a_worklist_with_nothing_on_it_reports_nothing(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """Every account here matched a roster row, so the "still needs a Member" list is empty,
    and an empty list has a total of zero rather than a phantom row the admin cannot find."""
    assert client.get(ME, headers=admin_headers).status_code == 200
    assert client.get(ME, headers=member_anna["headers"]).status_code == 200

    unbound = client.get(ACCOUNTS, params={"unbound": True}, headers=admin_headers).json()
    assert unbound["items"] == []
    assert unbound["total"] == 0


def test_signing_in_still_works_when_the_roster_row_is_already_taken(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """An admin has bound Anna's roster row to somebody else's account by hand. When Anna
    herself signs in, the bind that follows her e-mail match cannot succeed, and the platform
    promises the sign-in works anyway: she gets an account, unbound, and can still read the
    directory. The failed bind must not take the rest of the request down with it."""
    newbie = auth("newbie@cdtm.com")
    account_id = client.get(ME, headers=newbie).json()["account"]["id"]
    bound = client.post(
        f"{ACCOUNTS}/{account_id}/bind", json={"member_slug": "anna-test"}, headers=admin_headers
    )
    assert bound.status_code == 200, bound.text

    # Anna's first sign-in, on a request that reads the directory afterwards on the same
    # database session the failed bind ran on.
    directory = client.get("/api/v1/members/", headers=member_anna["headers"])
    assert directory.status_code == 200, directory.text

    me = client.get(ME, headers=member_anna["headers"])
    assert me.status_code == 200, me.text
    assert me.json()["member_id"] is None
    assert me.json()["account"]["email"] == member_anna["email"]


def test_an_account_with_no_member_is_told_how_to_get_one(client: TestClient) -> None:
    """Everything member-owned is closed to an account no roster row matched. The refusal has
    to say what to do about it, because the person cannot fix it themselves."""
    refused = client.get("/api/v1/members/me", headers=auth("unlinked@cdtm.com"))

    assert refused.status_code == 403, refused.text
    error = refused.json()["error"]
    assert error["code"] == "forbidden"
    assert "hint" in error["details"]


# ---- the development login, driven by the slug --------------------------------------------


def test_signing_in_by_slug_alone_uses_the_members_own_address(client: TestClient) -> None:
    """The picker only knows the slug. The address behind it is read off the roster row, and
    a member who already has one must be bound to that mailbox and not to a made-up one."""
    insert_member("carla-test", "Carla Test", "carla.test@cdtm.com")

    body = client.post(LOGIN, json={"member_slug": "carla-test"})

    assert body.status_code == 200, body.text
    me = body.json()["me"]
    assert me["member_slug"] == "carla-test"
    assert me["account"]["email"] == "carla.test@cdtm.com"
    # The name comes off the roster row, so the account is recognisable in the admin list.
    assert me["account"]["full_name"] == "Carla Test"
    assert _member_email("carla-test") == "carla.test@cdtm.com"


def test_signing_in_by_slug_alone_claims_a_member_that_has_no_address(
    client: TestClient,
) -> None:
    """This is what lets a developer become one of the roughly 175 Members who never had a
    mailbox: the address is derived from the slug and written onto the row."""
    insert_member("dan-test", "Dan Test")

    body = client.post(LOGIN, json={"member_slug": "dan-test"})

    assert body.status_code == 200, body.text
    me = body.json()["me"]
    assert me["member_slug"] == "dan-test"
    assert me["account"]["email"] == "dan-test@cdtm.com"
    assert _member_email("dan-test") == "dan-test@cdtm.com"


def test_the_derived_address_lands_on_the_first_allowed_domain(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The derived address has to pass the same allow-list as any other, so it is claimed on
    the first configured domain rather than on a hardcoded one."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAIL_DOMAINS", "example.org,cdtm.com")
    reset_settings_caches()
    insert_member("erin-test", "Erin Test")

    body = client.post(LOGIN, json={"member_slug": "erin-test"})

    assert body.status_code == 200, body.text
    assert body.json()["me"]["account"]["email"] == "erin-test@example.org"
    assert _member_email("erin-test") == "erin-test@example.org"


def test_with_no_allow_list_the_derived_address_falls_back_to_the_default_domain(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deployment that allows every domain still has to claim the row somewhere; a bare
    comma is how an operator switches the allow-list off."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAIL_DOMAINS", ",")
    reset_settings_caches()
    insert_member("fred-test", "Fred Test")

    body = client.post(LOGIN, json={"member_slug": "fred-test"})

    assert body.status_code == 200, body.text
    assert body.json()["me"]["account"]["email"] == "fred-test@cdtm.com"


def test_the_member_picker_hands_out_a_page_not_the_roster(client: TestClient) -> None:
    """The picker is unauthenticated. It is a type-ahead over the roster, and it must stay
    capped: without the limit reaching the query it would answer with every Member on the
    platform to anyone who can reach the port."""
    for index in range(MEMBER_PICKER_LIMIT + 5):
        insert_member(f"picker-{index:02d}", f"Picker {index:02d}")

    options = client.get("/api/v1/auth/dev/members")

    assert options.status_code == 200, options.text
    assert len(options.json()) == MEMBER_PICKER_LIMIT
