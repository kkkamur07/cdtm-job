"""Who counts as the organiser of an event, and who gets to see a draft.

The calendar's routes are all behind a signed-in Account, so these two rules are only ever
reached with an Actor in hand there. They are written to hold for no Actor at all as well
(``EventService`` passes one through from every caller, and an Account that is not linked to
a Member carries ``member_id=None``), and that is the case no route can produce, so it is
asserted directly.
"""

from datetime import timedelta
from uuid import uuid4

from backend.core.actor import Actor
from backend.events.application.event_service import _is_organiser, _is_visible
from backend.events.domain import Event, EventKind
from infrastructure.repository import utc_now

ORGANISER_ID = uuid4()
ANONYMOUS = None
UNBOUND = Actor(None)


def event(**overrides) -> Event:
    now = utc_now()
    fields = {
        "id": uuid4(),
        "title": "Stammtisch",
        "kind": EventKind.COMMUNITY,
        "starts_at": now + timedelta(days=3),
        "created_by_member_id": ORGANISER_ID,
        "created_at": now,
        "updated_at": now,
    }
    return Event(**(fields | overrides))


def test_nobody_and_an_account_without_a_member_are_not_the_organiser() -> None:
    ev = event()
    assert _is_organiser(ev, ANONYMOUS) is False
    assert _is_organiser(ev, UNBOUND) is False
    assert _is_organiser(ev, Actor(uuid4())) is False
    assert _is_organiser(ev, Actor(ORGANISER_ID)) is True


def test_an_authorless_event_has_no_organiser_to_match() -> None:
    """Both sides are nullable, so an unbound Account must never match an authorless row."""
    assert _is_organiser(event(created_by_member_id=None), UNBOUND) is False
    assert _is_organiser(event(created_by_member_id=None), ANONYMOUS) is False


def test_a_draft_is_visible_to_its_organiser_and_an_admin_and_to_nobody_else() -> None:
    draft = event(is_published=False)
    assert _is_visible(draft, ANONYMOUS) is False
    assert _is_visible(draft, UNBOUND) is False
    assert _is_visible(draft, Actor(uuid4())) is False
    assert _is_visible(draft, Actor(ORGANISER_ID)) is True
    assert _is_visible(draft, Actor(uuid4(), True)) is True


def test_a_published_event_is_visible_to_everyone_the_routes_let_in() -> None:
    published = event()
    assert _is_visible(published, ANONYMOUS) is True
    assert _is_visible(published, UNBOUND) is True
    assert _is_visible(published, Actor(uuid4())) is True
