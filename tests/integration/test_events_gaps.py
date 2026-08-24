"""The calendar: deleting, paging, counting RSVPs and what "upcoming" means.

Companion to ``test_events.py``, which covers the happy path of publishing and RSVPing.
What is here is the other half: who may *not* delete an event, that deleting one leaves the
rest of the calendar alone, that the two RSVP tallies are per event and per status, and that
an event which has begun but not finished is still on the calendar.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import auth, insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/events"


def _member(slug: str) -> dict:
    """Another signed-in Member, for the tests that need more than two."""
    email = f"{slug}@cdtm.com"
    return {
        "id": insert_member(slug, slug.replace("-", " ").title(), email),
        "headers": auth(email),
    }


def _when(**delta) -> str:
    return (datetime.now(UTC) + timedelta(**delta)).isoformat()


def _event(client: TestClient, headers: dict, **body) -> dict:
    payload = {"title": "Stammtisch", "starts_at": _when(days=3)} | body
    r = client.post(f"{API}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _ids(resp) -> list[str]:
    return [item["id"] for item in resp.json()["items"]]


def _why(resp) -> str:
    """The sentence a refusal gives the person who was refused."""
    return resp.json()["error"]["message"]


# ---- deleting -------------------------------------------------------------------------------


def test_only_the_organiser_or_an_admin_can_delete_an_event(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """A Member who is neither the organiser nor an admin has no say over somebody else's
    event, the same way they have no say over editing it."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    mine = _event(client, ha, title="Anna's mixer")
    theirs = _event(client, ha, title="Anna's other mixer")

    refused = client.delete(f"{API}/{mine['id']}", headers=hb)
    assert refused.status_code == 403
    assert _why(refused) == "only the organiser or an admin can delete this event"
    assert client.get(f"{API}/{mine['id']}", headers=hb).status_code == 200
    missing = client.delete(f"{API}/{uuid.uuid4()}", headers=ha)
    assert missing.status_code == 404
    assert _why(missing) == "event not found"

    edit = client.patch(f"{API}/{mine['id']}", json={"title": "Ben's now"}, headers=hb)
    assert edit.status_code == 403
    assert _why(edit) == "only the organiser or an admin can edit this event"
    gone = client.patch(f"{API}/{uuid.uuid4()}", json={"title": "Nowhere"}, headers=ha)
    assert gone.status_code == 404
    assert _why(gone) == "event not found"

    assert client.delete(f"{API}/{mine['id']}", headers=ha).status_code == 204
    assert client.delete(f"{API}/{theirs['id']}", headers=admin_headers).status_code == 204


def test_deleting_one_event_leaves_the_rest_of_the_calendar_alone(
    client: TestClient, member_anna: dict
) -> None:
    ha = member_anna["headers"]
    doomed = _event(client, ha, title="Cancelled talk")
    keeper = _event(client, ha, title="Stammtisch")

    assert client.delete(f"{API}/{doomed['id']}", headers=ha).status_code == 204

    assert client.get(f"{API}/{doomed['id']}", headers=ha).status_code == 404
    assert client.get(f"{API}/{keeper['id']}", headers=ha).status_code == 200
    listed = client.get(f"{API}/", headers=ha)
    assert _ids(listed) == [keeper["id"]] and listed.json()["total"] == 1


def test_the_organiser_can_edit_rsvp_to_and_delete_their_own_draft(
    client: TestClient, member_anna: dict
) -> None:
    """A draft is invisible to everyone else, but its organiser is not a stranger to it."""
    ha = member_anna["headers"]
    draft = _event(client, ha, title="Draft mixer", is_published=False)

    r = client.patch(f"{API}/{draft['id']}", json={"location": "Munich"}, headers=ha)
    assert r.status_code == 200, r.text
    r = client.put(f"{API}/{draft['id']}/rsvp", json={"status": "going"}, headers=ha)
    assert r.status_code == 200, r.text
    assert client.delete(f"{API}/{draft['id']}", headers=ha).status_code == 204


# ---- RSVP tallies ---------------------------------------------------------------------------


def test_the_two_rsvp_tallies_are_per_event_and_per_status(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """ "Going" and "interested" are different answers and different numbers, and neither is
    borrowed from the event next to it."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    carla, dora = _member("carla-test"), _member("dora-test")
    busy = _event(client, ha, title="Stammtisch")
    quiet = _event(client, ha, title="Workshop")

    client.put(f"{API}/{busy['id']}/rsvp", json={"status": "going"}, headers=hb)
    client.put(f"{API}/{busy['id']}/rsvp", json={"status": "interested"}, headers=carla["headers"])
    client.put(f"{API}/{busy['id']}/rsvp", json={"status": "interested"}, headers=dora["headers"])
    client.put(f"{API}/{quiet['id']}/rsvp", json={"status": "going"}, headers=carla["headers"])

    seen = client.get(f"{API}/{busy['id']}", headers=ha).json()
    assert (seen["going_count"], seen["interested_count"]) == (1, 2)
    seen = client.get(f"{API}/{quiet['id']}", headers=ha).json()
    assert (seen["going_count"], seen["interested_count"]) == (1, 0)

    # The same two numbers reach the calendar itself, not just the single event.
    listed = {item["id"]: item for item in client.get(f"{API}/", headers=ha).json()["items"]}
    assert (listed[busy["id"]]["going_count"], listed[busy["id"]]["interested_count"]) == (1, 2)
    assert (listed[quiet["id"]]["going_count"], listed[quiet["id"]]["interested_count"]) == (1, 0)


def test_changing_your_mind_replaces_your_answer_rather_than_adding_one(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    ev = _event(client, ha, title="Stammtisch")

    client.put(f"{API}/{ev['id']}/rsvp", json={"status": "going"}, headers=hb)
    changed = client.put(f"{API}/{ev['id']}/rsvp", json={"status": "interested"}, headers=hb)
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["going_count"], body["interested_count"]) == (0, 1)
    assert body["my_rsvp"] == "interested"


def test_my_rsvp_is_the_viewers_own_answer_to_that_one_event(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    answered = _event(client, ha, title="Stammtisch")
    unanswered = _event(client, ha, title="Workshop")
    client.put(f"{API}/{answered['id']}/rsvp", json={"status": "interested"}, headers=hb)

    mine = {
        item["id"]: item["my_rsvp"] for item in client.get(f"{API}/", headers=hb).json()["items"]
    }
    assert mine == {answered["id"]: "interested", unanswered["id"]: None}
    # Anna answered neither, and does not inherit Ben's answer.
    theirs = {
        item["id"]: item["my_rsvp"] for item in client.get(f"{API}/", headers=ha).json()["items"]
    }
    assert theirs == {answered["id"]: None, unanswered["id"]: None}
    assert client.get(f"{API}/{answered['id']}", headers=hb).json()["my_rsvp"] == "interested"
    assert client.get(f"{API}/{unanswered['id']}", headers=hb).json()["my_rsvp"] is None


# ---- what "upcoming" means -------------------------------------------------------------------


def test_an_event_that_has_started_but_not_finished_is_still_upcoming(
    client: TestClient, member_anna: dict
) -> None:
    """A conference is not over on its second morning: the calendar reads the end of an
    event when it has one, and its start when it does not."""
    ha = member_anna["headers"]
    ongoing = _event(
        client, ha, title="Two day summit", starts_at=_when(hours=-6), ends_at=_when(hours=6)
    )
    later = _event(client, ha, title="Next week", starts_at=_when(days=7))
    _event(client, ha, title="Finished", starts_at=_when(days=-2), ends_at=_when(days=-1))
    _event(client, ha, title="Yesterday, no end time", starts_at=_when(days=-1))

    upcoming = client.get(f"{API}/", params={"upcoming": True}, headers=ha)
    assert set(_ids(upcoming)) == {ongoing["id"], later["id"]}
    assert upcoming.json()["total"] == 2
    assert client.get(f"{API}/", params={"upcoming": False}, headers=ha).json()["total"] == 4


def test_the_calendar_pages_and_runs_from_the_next_event_to_the_furthest(
    client: TestClient, member_anna: dict
) -> None:
    ha = member_anna["headers"]
    # Created out of order on purpose: the calendar is ordered by when things happen.
    second = _event(client, ha, title="Second", starts_at=_when(days=2))
    third = _event(client, ha, title="Third", starts_at=_when(days=3))
    first = _event(client, ha, title="First", starts_at=_when(days=1))
    in_order = [first["id"], second["id"], third["id"]]

    assert _ids(client.get(f"{API}/", headers=ha)) == in_order
    for offset, expected in enumerate(in_order):
        page = client.get(f"{API}/", params={"skip": offset, "limit": 1}, headers=ha)
        assert _ids(page) == [expected]
        assert page.json()["total"] == 3
    # Looking back instead, the most recent one comes first.
    assert _ids(client.get(f"{API}/", params={"upcoming": False}, headers=ha)) == in_order[::-1]


# ---- the round trip ---------------------------------------------------------------------------


def test_an_event_keeps_every_field_it_was_published_with(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha = member_anna["headers"]
    starts, ends = _when(days=4), _when(days=4, hours=3)
    created = _event(
        client,
        ha,
        title="CDTM Demo Day",
        description="Fourteen teams, one evening.",
        kind="cdtm",
        starts_at=starts,
        ends_at=ends,
        location="Marsstrasse 20, Munich",
        url="https://cdtm.com/demoday",
    )

    fetched = client.get(f"{API}/{created['id']}", headers=member_ben["headers"]).json()
    assert fetched["title"] == "CDTM Demo Day"
    assert fetched["description"] == "Fourteen teams, one evening."
    assert fetched["kind"] == "cdtm"
    assert fetched["location"] == "Marsstrasse 20, Munich"
    assert fetched["url"] == "https://cdtm.com/demoday"
    assert datetime.fromisoformat(fetched["starts_at"]) == datetime.fromisoformat(starts)
    assert datetime.fromisoformat(fetched["ends_at"]) == datetime.fromisoformat(ends)
    assert fetched["created_by_member_id"] == str(member_anna["id"])

    listed = client.get(f"{API}/", headers=ha).json()["items"][0]
    assert listed["kind"] == "cdtm" and listed["location"] == "Marsstrasse 20, Munich"
    # The row is a summary: the description is only on the event itself, which the
    # assertion above already read. ``tests/integration/test_list_summaries.py`` is
    # where that split is pinned.
    assert "description" not in listed
    assert listed["url"] == "https://cdtm.com/demoday"
    assert datetime.fromisoformat(listed["ends_at"]) == datetime.fromisoformat(ends)


def test_an_event_can_be_moved_and_re_labelled_after_it_was_published(
    client: TestClient, member_anna: dict
) -> None:
    """Editing writes the same shapes creating does, ``kind`` included: it is one of three
    words the column is allowed to hold, not the enum object the request body became."""
    ha = member_anna["headers"]
    ev = _event(client, ha, title="Stammtisch", kind="community")
    moved = _when(days=9)

    r = client.patch(
        f"{API}/{ev['id']}",
        json={"kind": "external", "starts_at": moved, "location": "Berlin"},
        headers=ha,
    )
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "external"

    fetched = client.get(f"{API}/{ev['id']}", headers=ha).json()
    assert fetched["kind"] == "external"
    assert fetched["location"] == "Berlin"
    assert datetime.fromisoformat(fetched["starts_at"]) == datetime.fromisoformat(moved)
