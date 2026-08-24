"""The housing board: deleting a listing, paging it, and who is nobody's owner.

Companion to ``test_housing.py``. Deleting is covered here because it is the one action on a
listing that leaves nothing behind to inspect, so both halves have to be asserted: the
listing that was asked for is gone, and the one next to it is not.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import _engine, auth

pytestmark = pytest.mark.integration
API = "/api/v1/housing"

#: A signed-in Account whose e-mail is on no roster row: authenticated, bound to nobody.
UNBOUND = "newbie@cdtm.com"


def _listing(client: TestClient, headers: dict, **body) -> dict:
    payload = {"kind": "offer", "title": "Room in Schwabing", "city": "Munich"} | body
    r = client.post(f"{API}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _ids(resp) -> list[str]:
    return [item["id"] for item in resp.json()["items"]]


def _why(resp) -> str:
    """The sentence a refusal gives the person who was refused."""
    return resp.json()["error"]["message"]


def test_only_the_owner_or_an_admin_can_delete_a_listing(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    mine = _listing(client, ha, title="Anna's room")
    theirs = _listing(client, ha, title="Anna's other room")

    refused = client.delete(f"{API}/{mine['id']}", headers=hb)
    assert refused.status_code == 403
    assert _why(refused) == "only the owner or an admin can delete this listing"
    assert client.get(f"{API}/{mine['id']}", headers=hb).status_code == 200
    missing = client.delete(f"{API}/{uuid4()}", headers=ha)
    assert missing.status_code == 404
    assert _why(missing) == "listing not found"

    assert client.delete(f"{API}/{mine['id']}", headers=ha).status_code == 204
    assert client.delete(f"{API}/{theirs['id']}", headers=admin_headers).status_code == 204


def test_deleting_one_listing_leaves_the_rest_of_the_board_alone(
    client: TestClient, member_anna: dict
) -> None:
    ha = member_anna["headers"]
    doomed = _listing(client, ha, title="Room already taken")
    keeper = _listing(client, ha, title="Room still free")

    assert client.delete(f"{API}/{doomed['id']}", headers=ha).status_code == 204

    assert client.get(f"{API}/{doomed['id']}", headers=ha).status_code == 404
    assert client.get(f"{API}/{keeper['id']}", headers=ha).status_code == 200
    board = client.get(f"{API}/", headers=ha)
    assert _ids(board) == [keeper["id"]] and board.json()["total"] == 1
    # Deleting is not closing: it is gone for its owner too, with nothing left to renew.
    mine = client.get(f"{API}/", params={"member_id": member_anna["id"]}, headers=ha)
    assert _ids(mine) == [keeper["id"]]


def test_the_board_pages_and_shows_the_newest_listing_first(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    oldest = _listing(client, ha, title="Posted first")
    middle = _listing(client, ha, title="Posted second")
    newest = _listing(client, ha, title="Posted third")
    newest_first = [newest["id"], middle["id"], oldest["id"]]

    assert _ids(client.get(f"{API}/", headers=hb)) == newest_first
    for offset, expected in enumerate(newest_first):
        page = client.get(f"{API}/", params={"skip": offset, "limit": 1}, headers=hb)
        assert _ids(page) == [expected]
        # The count is the whole board, not the page.
        assert page.json()["total"] == 3


def test_a_listing_with_no_expiry_set_stays_on_the_board(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """Every listing the API writes gets an expiry, but a row that has none has not expired
    and must not fall off the board because it never had a date to compare."""
    listing = _listing(client, member_anna["headers"], title="Room with no expiry")
    with _engine.begin() as conn:
        conn.execute(
            text("update housing_listings set expires_at = null where id = :i"),
            {"i": listing["id"]},
        )
    assert _ids(client.get(f"{API}/", headers=member_ben["headers"])) == [listing["id"]]
    assert client.get(f"{API}/{listing['id']}", headers=member_ben["headers"]).status_code == 200


def test_the_furnished_words_are_read_in_the_description_as_well_as_the_title(
    client: TestClient, member_anna: dict
) -> None:
    """A listing written before the ``furnished`` column existed answers with its words, and
    people write "möbliert" in the description far more often than in the title."""
    h = member_anna["headers"]
    in_description = _listing(
        client, h, title="Room in Sendling", description="Ruhig, komplett möbliert, ab sofort."
    )
    plain = _listing(client, h, title="Room in Laim", description="Grosses Zimmer, Altbau.")

    furnished = client.get(f"{API}/", params={"furnished": True}, headers=h)
    assert _ids(furnished) == [in_description["id"]]
    unfurnished = client.get(f"{API}/", params={"furnished": False}, headers=h)
    assert _ids(unfurnished) == [plain["id"]]


def test_an_account_that_is_linked_to_no_member_owns_nothing(
    client: TestClient, member_anna: dict
) -> None:
    """A signed-in Account with no roster row has no member id, and a listing's owner column
    is never null: "neither of us has an id" must not read as "this is yours"."""
    ha = member_anna["headers"]
    unbound = auth(UNBOUND)
    open_listing = _listing(client, ha, title="Open room")
    closed = _listing(client, ha, title="Closed room")
    client.patch(f"{API}/{closed['id']}", json={"status": "closed"}, headers=ha)

    # Off the board is off the board for them, as for any other non-owner.
    assert client.get(f"{API}/{closed['id']}", headers=unbound).status_code == 404
    assert _ids(client.get(f"{API}/", headers=unbound)) == [open_listing["id"]]
    # And they are not shown the owner's view counter.
    assert client.get(f"{API}/{open_listing['id']}", headers=unbound).json()["view_count"] is None
    # Their reading counted, which is what tells the owner the post is being seen.
    assert client.get(f"{API}/{open_listing['id']}", headers=ha).json()["view_count"] == 1


def test_only_the_owner_or_an_admin_can_edit_or_renew_a_listing(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """Renewing pushes the expiry out, which is worth as much as editing the price: a
    stranger who could renew could keep somebody else's room on the board forever."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    listing = _listing(client, ha, title="Anna's room")

    refused = client.post(f"{API}/{listing['id']}/renew", headers=hb)
    assert refused.status_code == 403
    assert _why(refused) == "only the owner or an admin can renew this listing"
    edit = client.patch(f"{API}/{listing['id']}", json={"price_eur": 1}, headers=hb)
    assert edit.status_code == 403
    assert _why(edit) == "only the owner or an admin can edit this listing"
    missing = client.post(f"{API}/{uuid4()}/renew", headers=ha)
    assert missing.status_code == 404
    assert _why(missing) == "listing not found"

    before = client.get(f"{API}/{listing['id']}", headers=ha).json()["expires_at"]
    renewed = client.post(f"{API}/{listing['id']}/renew", headers=ha)
    assert renewed.status_code == 200, renewed.text
    assert datetime.fromisoformat(renewed.json()["expires_at"]) > datetime.fromisoformat(before)
    # An admin renews on a member's behalf, the same way they edit on it.
    assert client.post(f"{API}/{listing['id']}/renew", headers=admin_headers).status_code == 200
