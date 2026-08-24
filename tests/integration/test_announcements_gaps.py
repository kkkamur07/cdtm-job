"""What the board owes a reader: their own read state, their own badge, and an order.

``test_announcements.py`` proves the admin gate and that a read is recorded. It never lists
the board as two different members, never asks for a second page, never checks that the row
it fetched by id is the row it asked for, and never looks at any field of an announcement
beyond title and ``is_read``. Each of those is a way for one member's state to leak into
another's, or for the board to come back in the wrong order, with every existing test green.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import _engine, auth

pytestmark = pytest.mark.integration
API = "/api/v1/announcements"


def _post(client: TestClient, headers: dict, **body) -> dict:
    body.setdefault("title", "t")
    body.setdefault("body", "b")
    r = client.post(f"{API}/", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _titles(client: TestClient, headers: dict, **params) -> list[str]:
    r = client.get(f"{API}/", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return [item["title"] for item in r.json()["items"]]


def _by_title(client: TestClient, headers: dict) -> dict[str, dict]:
    r = client.get(f"{API}/", headers=headers)
    assert r.status_code == 200, r.text
    return {item["title"]: item for item in r.json()["items"]}


def test_a_read_receipt_belongs_to_one_member_and_one_announcement(
    client: TestClient, admin_headers: dict, member_anna: dict, member_ben: dict
) -> None:
    """Anna reading one notice must not mark it read for Ben, nor mark her other notices read.

    The per-viewer ``is_read`` flag and the ``read_count`` are two correlated subqueries over
    the same table, and either of them losing a clause is invisible while only one member
    ever reads only one announcement.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    first = _post(client, admin_headers, title="First", body="one")
    _post(client, admin_headers, title="Second", body="two")

    assert client.post(f"{API}/{first['id']}/read", headers=ha).status_code == 200

    anna = _by_title(client, ha)
    assert anna["First"]["is_read"] is True and anna["First"]["read_count"] == 1
    assert anna["Second"]["is_read"] is False and anna["Second"]["read_count"] == 0
    assert client.get(f"{API}/", headers=ha).json()["unread"] == 1

    ben = _by_title(client, hb)
    assert ben["First"]["is_read"] is False and ben["First"]["read_count"] == 1
    assert ben["Second"]["is_read"] is False
    assert client.get(f"{API}/", headers=hb).json()["unread"] == 2


def test_the_unread_badge_only_counts_what_is_on_the_board(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """A draft nobody can open, and an expired notice nobody can reach, are not unread."""
    h = member_anna["headers"]
    _post(client, admin_headers, title="Live", body="on the board")
    _post(client, admin_headers, title="Draft", body="not yet", published_at=None)
    expired = _post(client, admin_headers, title="Expired", body="gone")
    with _engine.begin() as conn:
        conn.execute(
            text("update announcements set expires_at = now() - interval '1 day' where id = :i"),
            {"i": expired["id"]},
        )

    body = client.get(f"{API}/", headers=h).json()
    assert body["total"] == 1 and body["unread"] == 1
    assert [item["title"] for item in body["items"]] == ["Live"]


def test_an_announcement_with_a_future_expiry_is_still_on_the_board(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """Setting an end date must not take a notice off the board before that date arrives."""
    h = member_anna["headers"]
    expires = (datetime.now(UTC) + timedelta(days=7)).replace(microsecond=0)
    ann = _post(client, admin_headers, title="Deadline", body="b", expires_at=expires.isoformat())

    assert ann["expires_at"] is not None
    assert datetime.fromisoformat(ann["expires_at"]) == expires

    body = client.get(f"{API}/", headers=h).json()
    assert body["total"] == 1 and body["unread"] == 1
    r = client.get(f"{API}/{ann['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert datetime.fromisoformat(r.json()["expires_at"]) == expires


def test_fetching_one_announcement_returns_the_one_that_was_asked_for(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    h = member_anna["headers"]
    first = _post(client, admin_headers, title="First", body="one")
    second = _post(client, admin_headers, title="Second", body="two")

    for ann in (first, second):
        r = client.get(f"{API}/{ann['id']}", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == ann["id"] and r.json()["title"] == ann["title"]


def test_an_edit_that_takes_a_notice_off_the_board_still_returns_the_edited_row(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """Expiring a notice is an ordinary edit; it must answer 200 with the row, not 404.

    The repository re-reads the row it just wrote, and it has to read it the way an admin
    would: the edit may well be the thing that made the row invisible to everybody else.
    """
    h = member_anna["headers"]
    ann = _post(client, admin_headers, title="Old news", body="b")
    past = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0)

    r = client.patch(
        f"{API}/{ann['id']}", json={"expires_at": past.isoformat()}, headers=admin_headers
    )
    assert r.status_code == 200, r.text
    assert datetime.fromisoformat(r.json()["expires_at"]) == past
    assert r.json()["id"] == ann["id"]

    assert client.get(f"{API}/{ann['id']}", headers=h).status_code == 404
    assert client.get(f"{API}/", headers=h).json()["total"] == 0


def test_the_board_is_pinned_first_and_then_newest_first(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """A pin outranks recency, and among equals the most recent notice is at the top."""
    h = member_anna["headers"]
    _post(client, admin_headers, title="Pinned", body="b", is_pinned=True)
    _post(client, admin_headers, title="Older", body="b")
    _post(client, admin_headers, title="Newer", body="b")

    assert _titles(client, h) == ["Pinned", "Newer", "Older"]


def test_a_notice_is_ordered_by_its_publication_date_not_by_when_it_was_written(
    client: TestClient, admin_headers: dict
) -> None:
    """A draft has no publication date, so it falls back to when it was written."""
    scheduled = _post(client, admin_headers, title="Scheduled", body="b")
    _post(client, admin_headers, title="Draft", body="b", published_at=None)
    with _engine.begin() as conn:
        conn.execute(
            text("update announcements set published_at = now() + interval '1 day' where id = :i"),
            {"i": scheduled["id"]},
        )

    assert _titles(client, admin_headers) == ["Scheduled", "Draft"]


def test_the_board_is_paged(client: TestClient, admin_headers: dict, member_anna: dict) -> None:
    h = member_anna["headers"]
    for title in ("First", "Second", "Third"):
        _post(client, admin_headers, title=title, body="b")

    body = client.get(f"{API}/", headers=h, params={"limit": 1}).json()
    assert body["total"] == 3 and [i["title"] for i in body["items"]] == ["Third"]
    assert _titles(client, h, skip=1, limit=1) == ["Second"]
    assert _titles(client, h, skip=2, limit=1) == ["First"]


def test_an_announcement_records_who_wrote_it_and_how_it_was_posted(
    client: TestClient, admin_headers: dict, member_anna: dict
) -> None:
    """Attribution and the pin are stored, not just accepted and dropped."""
    admin_member_id = client.get("/api/v1/auth/me", headers=admin_headers).json()["member_id"]
    ann = _post(client, admin_headers, title="Welcome", body="Hello", is_pinned=True)

    assert ann["author_member_id"] == admin_member_id
    assert ann["is_pinned"] is True
    assert ann["read_count"] == 0 and ann["is_read"] is False

    fetched = client.get(f"{API}/{ann['id']}", headers=member_anna["headers"]).json()
    assert fetched["author_member_id"] == admin_member_id
    assert fetched["is_pinned"] is True


def test_an_admin_can_mark_a_draft_read(client: TestClient, admin_headers: dict) -> None:
    """Reading is checked against what the reader may see, and an admin may see a draft."""
    draft = _post(client, admin_headers, title="Draft", body="b", published_at=None)
    r = client.post(f"{API}/{draft['id']}/read", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_read"] is True and r.json()["read_count"] == 1


def test_an_account_with_no_member_row_reads_the_board_without_a_badge(
    client: TestClient, admin_headers: dict
) -> None:
    """Signed in but not linked to anybody: there is no "you" to have read anything."""
    _post(client, admin_headers, title="Welcome", body="b")
    r = client.get(f"{API}/", headers=auth("unlinked.reader@cdtm.com"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1 and body["unread"] == 0
    assert body["items"][0]["is_read"] is False
