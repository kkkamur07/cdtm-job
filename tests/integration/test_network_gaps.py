"""Withdrawing an intro, both ends of an intro list, and the person on the other end.

``test_network.py`` walks one happy path: Anna saves Ben, asks Ben for an intro, Ben accepts.
It never withdraws a request, never looks at the list from the requester's side, never saves
two people, and never looks at any field of the card next to a saved row except the slug. So
the withdraw branch of ``respond_intro`` (who is allowed to do it), the requester half of the
``list_intros`` filter, and twelve of the thirteen columns of a member card are unverified.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.settings import get_database_settings
from backend.network.infrastructure.network_repository import SqlNetworkRepository
from tests.integration.conftest import insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/network"

#: Every card column with a value nothing else in the fixture shares, so a query that reads
#: the wrong column, or forgets one, cannot come back looking right.
CARD_COLUMNS = {
    "headline": "Building things at Plato",
    "avatar_sm_url": "https://cdn.example/carla-sm.webp",
    "avatar_lg_url": "https://cdn.example/carla-lg.webp",
    "avatar_blur": "data:image/webp;base64,carla-blur",
    "location": "Lisbon, Portugal",
    "class_label": "Fall 2019",
    "major": "Management & Technology",
    "current_company": "Plato",
    "current_title": "Co-Founder",
    "is_ca": True,
}


def _in_a_session(work: Any) -> Any:
    """Run ``work(session)`` on a throwaway engine of its own.

    The suite's ``client`` fixture owns a session-scoped event loop and an asyncpg pool bound
    to it, and a pool cannot be borrowed by a second loop. A test that needs to call a
    repository directly therefore brings its own engine and disposes of it again.
    """

    async def main():
        engine = create_async_engine(get_database_settings().async_url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(main())


def _saved_slugs(client: TestClient, headers: dict) -> list[str]:
    return [
        s["member"]["slug"] for s in client.get(f"{API}/saved", headers=headers).json()["items"]
    ]


def _request_intro(client: TestClient, headers: dict, target_id, message: str = "hi") -> dict:
    r = client.post(
        f"{API}/intros",
        json={"target_member_id": str(target_id), "message": message},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_only_the_requester_may_withdraw_an_intro_request(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """Withdrawing is the requester's power, the mirror image of accepting being the target's.

    Nothing exercised the withdraw branch before, so it could have been reading the wrong id,
    or answering "only an admin may", without a test noticing.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    intro = _request_intro(client, ha, member_ben["id"])

    # The target is the one person who may accept, and the one who may not withdraw.
    assert (
        client.post(
            f"{API}/intros/{intro['id']}/respond", json={"status": "withdrawn"}, headers=hb
        ).status_code
        == 403
    )

    r = client.post(f"{API}/intros/{intro['id']}/respond", json={"status": "withdrawn"}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "withdrawn"
    assert r.json()["responded_at"] is not None

    # Withdrawn is resolved: the target can no longer accept what was taken back.
    assert (
        client.post(
            f"{API}/intros/{intro['id']}/respond", json={"status": "accepted"}, headers=hb
        ).status_code
        == 409
    )


def test_an_intro_list_shows_both_the_ones_sent_and_the_ones_received(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    carl_id = insert_member("carl-test", "Carl Test", "carl.test@cdtm.com")
    ha, hb = member_anna["headers"], member_ben["headers"]

    _request_intro(client, ha, member_ben["id"], "first")
    _request_intro(client, ha, carl_id, "second")
    _request_intro(client, hb, member_anna["id"], "third")

    mine = client.get(f"{API}/intros", headers=ha).json()
    # Newest first, and both directions: Ben's request to Anna is in Anna's list too.
    assert mine["total"] == 3
    assert [v["request"]["message"] for v in mine["items"]] == ["third", "second", "first"]
    assert [v["target"]["slug"] for v in mine["items"]] == ["anna-test", "carl-test", "ben-test"]
    assert [v["requester"]["slug"] for v in mine["items"]] == [
        "ben-test",
        "anna-test",
        "anna-test",
    ]

    his = client.get(f"{API}/intros", headers=hb).json()
    assert [v["request"]["message"] for v in his["items"]] == ["third", "first"]

    # The page is a real page: the limit reaches the query and the total still counts
    # every row behind it, not the ones that came back.
    page = client.get(f"{API}/intros", params={"skip": 1, "limit": 1}, headers=ha).json()
    assert page["total"] == 3
    assert [v["request"]["message"] for v in page["items"]] == ["second"]


def test_saving_somebody_twice_rewrites_the_note_rather_than_failing(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha = member_anna["headers"]
    assert (
        client.put(
            f"{API}/saved/{member_ben['id']}", json={"note": "ask about VC"}, headers=ha
        ).json()["saved"]["note"]
        == "ask about VC"
    )
    r = client.put(f"{API}/saved/{member_ben['id']}", json={"note": "ask about hiring"}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["saved"]["note"] == "ask about hiring"

    saved = client.get(f"{API}/saved", headers=ha).json()
    assert saved["total"] == 1 and saved["items"][0]["saved"]["note"] == "ask about hiring"

    # And an empty note clears it rather than leaving the old one behind.
    assert client.put(f"{API}/saved/{member_ben['id']}", json={}, headers=ha).status_code == 200
    assert client.get(f"{API}/saved", headers=ha).json()["items"][0]["saved"]["note"] is None


def test_unsaving_one_person_leaves_every_other_saved_row_alone(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """The delete is keyed on both halves of the row: whose list, and who is in it."""
    carl_id = insert_member("carl-test", "Carl Test", "carl.test@cdtm.com")
    ha, hb = member_anna["headers"], member_ben["headers"]

    client.put(f"{API}/saved/{member_ben['id']}", json={}, headers=ha)
    client.put(f"{API}/saved/{carl_id}", json={}, headers=ha)
    client.put(f"{API}/saved/{carl_id}", json={}, headers=hb)

    # Most recently saved first.
    assert _saved_slugs(client, ha) == ["carl-test", "ben-test"]

    assert client.delete(f"{API}/saved/{carl_id}", headers=ha).status_code == 204
    assert _saved_slugs(client, ha) == ["ben-test"]
    assert _saved_slugs(client, hb) == ["carl-test"]
    # Anna already removed Carl; removing him twice is a 404, not somebody else's row.
    assert client.delete(f"{API}/saved/{carl_id}", headers=ha).status_code == 404


def test_the_shortlist_is_paged_rather_than_however_long_it_happens_to_be(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """``GET /network/saved`` used to be a bare list with no skip and no limit.

    Nothing bounded the body but how many people the member had saved. It pages like every
    other list now, and the skip and the limit go into the query rather than being applied
    to a response that was already fully built.
    """
    carl_id = insert_member("carl-test", "Carl Test", "carl.test@cdtm.com")
    ha = member_anna["headers"]
    client.put(f"{API}/saved/{member_ben['id']}", json={}, headers=ha)
    client.put(f"{API}/saved/{carl_id}", json={}, headers=ha)

    page = client.get(f"{API}/saved", params={"limit": 1}, headers=ha).json()
    # The total counts the whole shortlist, not the page that came back.
    assert page["total"] == 2
    assert [s["member"]["slug"] for s in page["items"]] == ["carl-test"]

    assert [
        s["member"]["slug"]
        for s in client.get(f"{API}/saved", params={"skip": 1, "limit": 1}, headers=ha).json()[
            "items"
        ]
    ] == ["ben-test"]

    # A page past the end is empty and still knows how many there are.
    beyond = client.get(f"{API}/saved", params={"skip": 50}, headers=ha).json()
    assert beyond == {"items": [], "total": 2}

    # And the cap on every other list applies here too.
    assert client.get(f"{API}/saved", params={"limit": 101}, headers=ha).status_code == 422


def test_a_saved_row_carries_a_whole_card_not_only_a_name(
    client: TestClient, member_anna: dict
) -> None:
    """Thirteen columns are read by position out of one query; all thirteen are shown."""
    carla_id = insert_member("carla-test", "Carla Test", "carla.test@cdtm.com", **CARD_COLUMNS)
    r = client.put(f"{API}/saved/{carla_id}", json={}, headers=member_anna["headers"])
    assert r.status_code == 200, r.text

    card = r.json()["member"]
    assert card == {
        "id": str(carla_id),
        "slug": "carla-test",
        "name": "Carla Test",
        "headline": CARD_COLUMNS["headline"],
        "avatar_sm_url": CARD_COLUMNS["avatar_sm_url"],
        "avatar_lg_url": CARD_COLUMNS["avatar_lg_url"],
        "avatar_blur": CARD_COLUMNS["avatar_blur"],
        "location": CARD_COLUMNS["location"],
        "class_label": CARD_COLUMNS["class_label"],
        "major": CARD_COLUMNS["major"],
        "company": CARD_COLUMNS["current_company"],
        "title": CARD_COLUMNS["current_title"],
        "is_ca": True,
    }
    listed = client.get(f"{API}/saved", headers=member_anna["headers"]).json()
    assert listed["total"] == 1 and listed["items"][0]["member"] == card


def test_one_saved_row_can_be_read_back_on_its_own(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """``NetworkRepository.get_saved`` answers "is this person in this member's list".

    It has no route of its own, so it is exercised here the way the loader scripts exercise
    a repository: against the real session, through the port's own contract.
    """
    carl_id = insert_member("carl-test", "Carl Test", "carl.test@cdtm.com")
    r = client.put(
        f"{API}/saved/{member_ben['id']}",
        json={"note": "ask about VC"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text

    async def work(session):
        repo = SqlNetworkRepository(session)
        return (
            await repo.get_saved(member_anna["id"], member_ben["id"]),
            await repo.get_saved(member_anna["id"], carl_id),
            await repo.get_saved(member_ben["id"], member_anna["id"]),
            await repo.get_saved(uuid.uuid4(), member_ben["id"]),
        )

    saved, not_saved, other_way_round, stranger = _in_a_session(work)
    assert saved is not None
    assert saved.owner_member_id == member_anna["id"]
    assert saved.saved_member_id == member_ben["id"]
    assert saved.note == "ask about VC"
    assert saved.created_at is not None
    # The row is keyed on both halves and is not symmetric.
    assert not_saved is None and other_way_round is None and stranger is None
