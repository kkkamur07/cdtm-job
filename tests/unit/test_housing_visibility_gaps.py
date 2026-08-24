"""The housing board's visibility rules, with nobody in particular looking.

``ActorDep`` hands the board an ``Actor`` for every signed-in Account, but an Account that
is not linked to a Member carries ``member_id=None``, and the rules are also called with no
Actor at all from application code. Neither caller may be mistaken for the owner of a
listing, so both are asserted here rather than left to the routes, which cannot produce the
second case at all.
"""

from datetime import timedelta
from uuid import uuid4

from backend.core.actor import Actor
from backend.housing.application.ports import HousingFilters
from backend.housing.application.visibility import (
    for_viewer,
    is_on_the_board,
    is_owner,
    sanitized_list_filters,
)
from backend.housing.domain import HousingKind, HousingListing, HousingStatus
from infrastructure.repository import utc_now

OWNER_ID = uuid4()
ANONYMOUS = None
UNBOUND = Actor(None)


def listing(**overrides) -> HousingListing:
    now = utc_now()
    fields = {
        "id": uuid4(),
        "member_id": OWNER_ID,
        "kind": HousingKind.OFFER,
        "title": "Room in Schwabing",
        "city": "Munich",
        "view_count": 7,
        "created_at": now,
        "updated_at": now,
    }
    return HousingListing(**(fields | overrides))


def test_nobody_and_an_account_without_a_member_are_not_the_owner() -> None:
    row = listing()
    assert is_owner(row, ANONYMOUS) is False
    assert is_owner(row, UNBOUND) is False
    assert is_owner(row, Actor(uuid4())) is False
    assert is_owner(row, Actor(OWNER_ID)) is True


def test_an_authorless_row_is_not_owned_by_an_account_without_a_member() -> None:
    """Both sides are nullable; two absent ids are not a match."""
    assert is_owner(listing(), UNBOUND) is False


def test_a_listing_that_left_the_board_is_gone_for_a_viewer_who_owns_nothing() -> None:
    closed = listing(status=HousingStatus.CLOSED)
    expired = listing(expires_at=utc_now() - timedelta(days=1))
    for viewer in (ANONYMOUS, UNBOUND):
        assert is_on_the_board(closed, viewer) is False
        assert is_on_the_board(expired, viewer) is False
        assert is_on_the_board(listing(), viewer) is True
    assert is_on_the_board(closed, Actor(OWNER_ID)) is True
    assert is_on_the_board(closed, Actor(uuid4(), True)) is True


def test_a_listing_with_no_expiry_is_on_the_board() -> None:
    assert is_on_the_board(listing(expires_at=None), UNBOUND) is True


def test_the_view_counter_is_hidden_from_a_viewer_who_owns_nothing() -> None:
    row = listing()
    assert for_viewer(row, ANONYMOUS).view_count is None
    assert for_viewer(row, UNBOUND).view_count is None
    assert for_viewer(row, Actor(OWNER_ID)).view_count == 7
    assert for_viewer(row, Actor(uuid4(), True)).view_count == 7
    # The rule copies, it does not edit: the row itself still carries the number.
    assert row.view_count == 7


def test_a_viewer_who_owns_nothing_is_held_to_the_open_board() -> None:
    asked = HousingFilters(status=HousingStatus.CLOSED, member_id=OWNER_ID, include_expired=True)
    for viewer in (ANONYMOUS, UNBOUND):
        held = sanitized_list_filters(asked, viewer)
        assert held.status is HousingStatus.OPEN
        assert not held.include_expired
        # Everything else the caller asked for survives.
        assert held.member_id == OWNER_ID
