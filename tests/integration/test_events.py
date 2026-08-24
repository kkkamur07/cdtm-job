"""Events and RSVPs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration
API = "/api/v1/events"


def test_events_and_rsvp(client: TestClient, member_anna: dict, member_ben: dict) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    starts = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    r = client.post(
        f"{API}/",
        json={"title": "Stammtisch", "starts_at": starts, "location": "Munich"},
        headers=ha,
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    r = client.put(f"{API}/{ev['id']}/rsvp", json={"status": "going"}, headers=hb)
    assert r.json()["going_count"] == 1 and r.json()["my_rsvp"] == "going"
    r = client.get(f"{API}/", headers=ha)
    assert r.json()["total"] == 1 and r.json()["items"][0]["my_rsvp"] is None
    # only organiser/admin edits
    assert client.patch(f"{API}/{ev['id']}", json={"title": "x"}, headers=hb).status_code == 403
    assert (
        client.patch(
            f"{API}/{ev['id']}", json={"title": "Stammtisch Munich"}, headers=ha
        ).status_code
        == 200
    )
    # clearing RSVP
    r = client.put(f"{API}/{ev['id']}/rsvp", json={"status": None}, headers=hb)
    assert r.json()["going_count"] == 0
    assert client.delete(f"{API}/{ev['id']}", headers=ha).status_code == 204


def test_unpublished_event_is_not_readable_or_rsvpable_by_non_owner(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """A draft is not on the board and not fetchable by id either -- see events/CONTEXT.md
    "Published" -- so it must not be readable or RSVP-able by anyone but its organiser or an
    admin, and anon has no route in at all (reading the calendar requires being signed in).
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    starts = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    r = client.post(
        f"{API}/",
        json={"title": "Draft mixer", "starts_at": starts, "is_published": False},
        headers=ha,
    )
    assert r.status_code == 201, r.text
    ev = r.json()

    # Anon has no signed-in Account at all: unauthenticated, not merely disallowed.
    assert client.get(f"{API}/{ev['id']}").status_code == 401
    assert client.get(f"{API}/").status_code == 401

    # Another Member cannot see it exists...
    assert client.get(f"{API}/{ev['id']}", headers=hb).status_code == 404
    assert client.get(f"{API}/", headers=hb).json()["total"] == 0
    # ...and cannot RSVP to it either.
    assert (
        client.put(f"{API}/{ev['id']}/rsvp", json={"status": "going"}, headers=hb).status_code
        == 404
    )

    # The organiser and an admin still see it.
    assert client.get(f"{API}/{ev['id']}", headers=ha).status_code == 200
    assert client.get(f"{API}/{ev['id']}", headers=admin_headers).status_code == 200
