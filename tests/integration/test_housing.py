"""Housing listings: filtering, editing, expiry and renewal, and the view counter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import _engine

pytestmark = pytest.mark.integration
API = "/api/v1/housing"


def test_housing_listings(client: TestClient, member_anna: dict, member_ben: dict) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    r = client.post(
        f"{API}/",
        json={
            "kind": "offer",
            "title": "Room in Maxvorstadt",
            "city": "Munich",
            "price_eur": 780,
            "rooms": 1,
        },
        headers=ha,
    )
    assert r.status_code == 201, r.text
    listing = r.json()
    assert client.get(f"{API}/", params={"kind": "looking"}, headers=hb).json()["total"] == 0
    assert client.get(f"{API}/", params={"city": "mun"}, headers=hb).json()["total"] == 1
    assert (
        client.patch(f"{API}/{listing['id']}", json={"status": "closed"}, headers=hb).status_code
        == 403
    )
    r = client.patch(f"{API}/{listing['id']}", json={"status": "closed"}, headers=ha)
    assert r.json()["status"] == "closed"
    assert client.get(f"{API}/", headers=hb).json()["total"] == 0  # default status=open


def test_housing_listing_expiry_and_renew(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    r = client.post(
        f"{API}/",
        json={"kind": "looking", "title": "Room wanted", "city": "Berlin"},
        headers=ha,
    )
    listing = r.json()
    expires = datetime.fromisoformat(listing["expires_at"])
    assert timedelta(days=59) < expires - datetime.now(UTC) <= timedelta(days=60)
    # Expired listings leave the board but stay visible to their owner, who can renew.
    with _engine.begin() as conn:
        conn.execute(
            text("update housing_listings set expires_at = now() - interval '1 day' where id = :i"),
            {"i": listing["id"]},
        )
    assert client.get(f"{API}/", headers=hb).json()["total"] == 0
    mine = client.get(f"{API}/", params={"member_id": member_anna["id"]}, headers=ha)
    assert mine.json()["total"] == 1
    assert client.post(f"{API}/{listing['id']}/renew", headers=hb).status_code == 403
    r = client.post(f"{API}/{listing['id']}/renew", headers=ha)
    assert r.status_code == 200, r.text
    assert datetime.fromisoformat(r.json()["expires_at"]) > datetime.now(UTC) + timedelta(days=59)
    assert client.get(f"{API}/", headers=hb).json()["total"] == 1


def test_furnished_filter_uses_the_column_and_falls_back_to_the_words(
    client: TestClient, member_anna: dict
) -> None:
    """A listing that answered the question is taken at its word; an old one is read."""
    h = member_anna["headers"]
    said_yes = client.post(
        f"{API}/",
        json={"kind": "offer", "title": "Bright room", "city": "Munich", "furnished": True},
        headers=h,
    ).json()
    said_no = client.post(
        f"{API}/",
        json={
            "kind": "offer",
            "title": "Furnished sounding but empty",
            "city": "Munich",
            "furnished": False,
        },
        headers=h,
    ).json()
    never_asked = client.post(
        f"{API}/",
        json={"kind": "offer", "title": "Room, fully furnished", "city": "Munich"},
        headers=h,
    ).json()
    assert said_yes["furnished"] is True
    assert never_asked["furnished"] is None

    slugs = lambda body: {item["id"] for item in body["items"]}  # noqa: E731
    yes = client.get(f"{API}/", params={"furnished": True}, headers=h).json()
    assert slugs(yes) == {said_yes["id"], never_asked["id"]}
    no = client.get(f"{API}/", params={"furnished": False}, headers=h).json()
    assert slugs(no) == {said_no["id"]}


def test_view_count_counts_other_people_and_is_shown_only_to_the_owner(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    listing = client.post(
        f"{API}/",
        json={"kind": "offer", "title": "Room in Sendling", "city": "Munich"},
        headers=ha,
    ).json()
    assert listing["view_count"] == 0

    # The owner opening their own listing is not a view, and neither is an admin's.
    assert client.get(f"{API}/{listing['id']}", headers=ha).json()["view_count"] == 0
    assert client.get(f"{API}/{listing['id']}", headers=admin_headers).json()["view_count"] == 0

    # Somebody else is, but they are not told the number.
    assert client.get(f"{API}/{listing['id']}", headers=hb).json()["view_count"] is None
    client.get(f"{API}/{listing['id']}", headers=hb)
    assert client.get(f"{API}/{listing['id']}", headers=ha).json()["view_count"] == 2
    # It reaches the owner's list too, which is where the renew decision is made.
    mine = client.get(f"{API}/", params={"member_id": member_anna["id"]}, headers=ha).json()
    assert mine["items"][0]["view_count"] == 2


def test_board_requires_a_signed_in_account(client: TestClient) -> None:
    """ "Every read on this board is behind a signed-in Account" (housing/api/housing.py):
    a Listing names a city, a street, a price and a date somebody's room is free, written
    for other Members and not for the internet.
    """
    assert client.get(f"{API}/").status_code == 401
    assert client.get(f"{API}/{uuid4()}").status_code == 401


def test_closed_and_expired_listings_are_off_the_board_for_everyone_but_owner_and_admin(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """housing/CONTEXT.md "Status" / "Expiry": Status is a decision the Owner made, Expiry is
    time passing, and either way "the board simply stops showing it" for anyone but the
    Owner or an admin -- by id, and not only via the plain list.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    closed = client.post(
        f"{API}/", json={"kind": "offer", "title": "Closed room", "city": "Munich"}, headers=ha
    ).json()
    client.patch(f"{API}/{closed['id']}", json={"status": "closed"}, headers=ha)

    expired = client.post(
        f"{API}/", json={"kind": "offer", "title": "Expired room", "city": "Munich"}, headers=ha
    ).json()
    with _engine.begin() as conn:
        conn.execute(
            text("update housing_listings set expires_at = now() - interval '1 day' where id = :i"),
            {"i": expired["id"]},
        )

    for listing_id in (closed["id"], expired["id"]):
        assert client.get(f"{API}/{listing_id}", headers=hb).status_code == 404
        assert client.get(f"{API}/{listing_id}", headers=ha).status_code == 200
        assert client.get(f"{API}/{listing_id}", headers=admin_headers).status_code == 200


def test_member_id_filter_cannot_be_used_to_see_someone_elses_closed_or_expired_listings(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """The ``member_id`` filter exists so "my listings" can show what there is to renew
    (housing/CONTEXT.md "Renew"), not so any Member can point it at someone else's id and
    read what :func:`is_on_the_board` would refuse them by id. Neither should
    ``status=closed`` on the plain board, with no ``member_id`` at all, hand back rows that
    belong to somebody else.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    open_listing = client.post(
        f"{API}/", json={"kind": "offer", "title": "Open room", "city": "Munich"}, headers=ha
    ).json()
    closed = client.post(
        f"{API}/", json={"kind": "offer", "title": "Closed room", "city": "Munich"}, headers=ha
    ).json()
    client.patch(f"{API}/{closed['id']}", json={"status": "closed"}, headers=ha)
    expired = client.post(
        f"{API}/", json={"kind": "offer", "title": "Expired room", "city": "Munich"}, headers=ha
    ).json()
    with _engine.begin() as conn:
        conn.execute(
            text("update housing_listings set expires_at = now() - interval '1 day' where id = :i"),
            {"i": expired["id"]},
        )

    def ids(resp) -> set[str]:
        return {item["id"] for item in resp.json()["items"]}

    # B pointing member_id at Anna sees only what is actually on the board.
    r = client.get(f"{API}/", params={"member_id": member_anna["id"]}, headers=hb)
    assert ids(r) == {open_listing["id"]}
    # ...even when B explicitly asks for the closed ones: the request is held to "open"
    # rather than honoured, so B still gets Anna's open listing and never the closed one.
    r = client.get(
        f"{API}/", params={"member_id": member_anna["id"], "status": "closed"}, headers=hb
    )
    assert ids(r) == {open_listing["id"]}
    # B asking the whole board for status=closed does not see Anna's closed listing either.
    r = client.get(f"{API}/", params={"status": "closed"}, headers=hb)
    assert closed["id"] not in ids(r)

    # Anna, looking at her own id, still gets the "my listings" view she needs to renew.
    r = client.get(
        f"{API}/", params={"member_id": member_anna["id"], "status": "closed"}, headers=ha
    )
    assert ids(r) == {closed["id"]}
    r = client.get(f"{API}/", params={"member_id": member_anna["id"]}, headers=ha)
    assert ids(r) == {open_listing["id"], expired["id"]}

    # An admin is trusted with the same requests Anna is.
    r = client.get(f"{API}/", params={"status": "closed"}, headers=admin_headers)
    assert ids(r) == {closed["id"]}
