"""Announcements: admin only to write, read tracking per member."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import _engine

pytestmark = pytest.mark.integration
API = "/api/v1/announcements"


def test_announcements_admin_only_and_read_tracking(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    h = member_anna["headers"]
    assert client.post(f"{API}/", json={"title": "t", "body": "b"}, headers=h).status_code == 403
    r = client.post(
        f"{API}/",
        json={"title": "Welcome", "body": "Hello", "is_pinned": True},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    ann = r.json()
    assert ann["published_at"] is not None
    r = client.get(f"{API}/", headers=h)
    assert (
        r.json()["total"] == 1
        and r.json()["unread"] == 1
        and r.json()["items"][0]["is_read"] is False
    )
    r = client.post(f"{API}/{ann['id']}/read", headers=h)
    assert r.json()["is_read"] is True and r.json()["read_count"] == 1
    assert client.get(f"{API}/", headers=h).json()["unread"] == 0
    # unpublished draft hidden from members, visible to admin
    r = client.post(
        f"{API}/",
        json={"title": "Draft", "body": "x", "published_at": None},
        headers=admin_headers,
    )
    assert client.get(f"{API}/", headers=h).json()["total"] == 1
    assert client.get(f"{API}/", headers=admin_headers).json()["total"] == 2


def test_expired_announcement_is_hidden_from_members_but_admin_still_sees_it(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """Expires at is about the board, not the archive (announcements/CONTEXT.md "Expires at"):
    the row is never deleted, but an ordinary Member must stop being able to reach it, by id
    or by list, once its window has passed. Only an Admin is shown anything outside the
    window (CONTEXT.md "Visible").
    """
    h = member_anna["headers"]
    r = client.post(
        f"{API}/", json={"title": "Old news", "body": "Stale by now"}, headers=admin_headers
    )
    assert r.status_code == 201, r.text
    ann = r.json()
    with _engine.begin() as conn:
        conn.execute(
            text("update announcements set expires_at = now() - interval '1 day' where id = :i"),
            {"i": ann["id"]},
        )

    assert client.get(f"{API}/{ann['id']}", headers=h).status_code == 404
    assert client.get(f"{API}/", headers=h).json()["total"] == 0

    assert client.get(f"{API}/{ann['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"{API}/", headers=admin_headers).json()["total"] == 1


def test_editing_and_removing_an_announcement_is_admin_only(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """Editing and removing a notice are admin powers, the same as posting one.

    Nothing exercised the PATCH or DELETE gates before, so an inverted admin check on either
    would have let any Member rewrite or erase a board announcement undetected.
    """
    h = member_anna["headers"]
    ann = client.post(
        f"{API}/", json={"title": "First", "body": "Original"}, headers=admin_headers
    ).json()

    # A non-admin can neither edit nor delete, and nothing changes.
    assert (
        client.patch(f"{API}/{ann['id']}", json={"title": "Hijacked"}, headers=h).status_code == 403
    )
    assert client.delete(f"{API}/{ann['id']}", headers=h).status_code == 403
    assert client.get(f"{API}/{ann['id']}", headers=admin_headers).json()["title"] == "First"

    # An admin can edit, and the change persists.
    r = client.patch(f"{API}/{ann['id']}", json={"title": "Second"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Second"
    assert client.get(f"{API}/{ann['id']}", headers=admin_headers).json()["title"] == "Second"

    # Editing or deleting an id that does not exist is a 404, not a silent success.
    assert (
        client.patch(f"{API}/{ann['id']}", json={"title": "x"}, headers=admin_headers).status_code
        == 200
    )
    assert client.delete(f"{API}/{uuid4()}", headers=admin_headers).status_code == 404
    assert (
        client.patch(f"{API}/{uuid4()}", json={"title": "x"}, headers=admin_headers).status_code
        == 404
    )

    # An admin can delete, and it is then gone for everyone.
    assert client.delete(f"{API}/{ann['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{API}/{ann['id']}", headers=admin_headers).status_code == 404
