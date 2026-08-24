"""EntryService against fakes: whose Entry and Intents a caller is allowed to touch.

The service documents "a member edits their own Entry and Intents; admins may edit
anyone's". No HTTP route passes a ``member_id`` today (``backend/members/api/me.py`` always
edits the caller's own), so the admin override is only reachable from here, which is
exactly why it is tested here.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.members.application.commands import EntryUpsert, IntentsUpsert
from backend.members.application.entry_service import EntryService
from backend.members.domain import MemberEntry, MemberIntents, MemberProfile


class _Entries:
    """An entry/intents store keyed by member id, so a misdirected write is visible."""

    def __init__(self) -> None:
        self.entries: dict[UUID, MemberEntry] = {}
        self.intents: dict[UUID, MemberIntents] = {}

    async def get(self, member_id: UUID) -> MemberEntry | None:
        return self.entries.get(member_id)

    async def upsert(self, member_id: UUID, payload: EntryUpsert) -> MemberEntry:
        entry = MemberEntry(member_id=member_id, ask_me_about=payload.ask_me_about)
        self.entries[member_id] = entry
        return entry

    async def get_intents(self, member_id: UUID) -> MemberIntents | None:
        return self.intents.get(member_id)

    async def upsert_intents(self, member_id: UUID, payload: IntentsUpsert) -> MemberIntents:
        intents = MemberIntents(note=payload.note, mentoring=bool(payload.mentoring))
        self.intents[member_id] = intents
        return intents


class _Members:
    def __init__(self, *known: UUID) -> None:
        self.known = set(known)

    async def get_by_id(self, member_id: UUID) -> MemberProfile | None:
        if member_id not in self.known:
            return None
        return MemberProfile(id=member_id, slug=f"member-{member_id}", name="Known Member")


ANNA = uuid4()
BEN = uuid4()
MISSING = uuid4()


def _service() -> tuple[EntryService, _Entries]:
    entries = _Entries()
    return EntryService(entries, _Members(ANNA, BEN)), entries


async def test_a_member_maintains_their_own_entry_and_intents() -> None:
    """The ordinary case: no member id named, so the caller's own record is the target."""
    service, store = _service()
    anna = Actor(ANNA)

    assert await service.get_entry(anna) is None
    assert await service.get_intents(anna) is None

    entry = await service.upsert_entry(anna, EntryUpsert(ask_me_about="fundraising"))
    intents = await service.upsert_intents(anna, IntentsUpsert(mentoring=True, note="pre-seed"))

    assert entry.member_id == ANNA
    assert store.entries.keys() == {ANNA}
    assert store.intents.keys() == {ANNA}
    assert intents.mentoring is True
    assert (await service.get_entry(anna)).ask_me_about == "fundraising"
    assert (await service.get_intents(anna)).note == "pre-seed"


async def test_naming_your_own_id_is_the_same_as_naming_nobody() -> None:
    """A member who passes their own id is not asking for the admin override."""
    service, store = _service()
    anna = Actor(ANNA)

    await service.upsert_entry(anna, EntryUpsert(ask_me_about="B2B sales"), member_id=ANNA)
    await service.upsert_intents(anna, IntentsUpsert(note="only me"), member_id=ANNA)

    assert store.entries.keys() == {ANNA}
    assert store.intents.keys() == {ANNA}
    assert (await service.get_entry(anna, member_id=ANNA)).ask_me_about == "B2B sales"
    assert (await service.get_intents(anna, member_id=ANNA)).note == "only me"


async def test_a_member_cannot_reach_another_members_entry_or_intents() -> None:
    """Attack: Anna asks for Ben's private Entry by id. Every door is the same door."""
    service, store = _service()
    anna = Actor(ANNA)

    with pytest.raises(ForbiddenError):
        await service.get_entry(anna, member_id=BEN)
    with pytest.raises(ForbiddenError):
        await service.upsert_entry(anna, EntryUpsert(ask_me_about="x"), member_id=BEN)
    with pytest.raises(ForbiddenError):
        await service.get_intents(anna, member_id=BEN)
    with pytest.raises(ForbiddenError):
        await service.upsert_intents(anna, IntentsUpsert(hiring=True), member_id=BEN)

    assert store.entries == {} and store.intents == {}


async def test_an_admin_reads_and_edits_another_members_entry_and_intents() -> None:
    """The override the class docstring promises, and it lands on the named member."""
    service, store = _service()
    admin = Actor(ANNA, is_admin=True)

    entry = await service.upsert_entry(
        admin, EntryUpsert(ask_me_about="ben's topic"), member_id=BEN
    )
    intents = await service.upsert_intents(admin, IntentsUpsert(note="ben's note"), member_id=BEN)

    assert entry.member_id == BEN
    assert store.entries.keys() == {BEN}, "an admin's edit landed on the wrong member"
    assert store.intents.keys() == {BEN}
    assert intents.note == "ben's note"
    assert (await service.get_entry(admin, member_id=BEN)).ask_me_about == "ben's topic"
    assert (await service.get_intents(admin, member_id=BEN)).note == "ben's note"
    # The admin's own records were not touched by editing somebody else's.
    assert await service.get_entry(admin) is None
    assert await service.get_intents(admin) is None


async def test_an_admin_editing_a_member_who_does_not_exist_is_a_not_found() -> None:
    service, store = _service()
    admin = Actor(ANNA, is_admin=True)

    with pytest.raises(NotFoundError):
        await service.get_entry(admin, member_id=MISSING)
    with pytest.raises(NotFoundError):
        await service.upsert_entry(admin, EntryUpsert(ask_me_about="x"), member_id=MISSING)
    with pytest.raises(NotFoundError):
        await service.get_intents(admin, member_id=MISSING)
    with pytest.raises(NotFoundError):
        await service.upsert_intents(admin, IntentsUpsert(hiring=True), member_id=MISSING)

    assert store.entries == {} and store.intents == {}


async def test_an_account_not_linked_to_a_member_has_no_entry_to_edit() -> None:
    service, _ = _service()
    nobody = Actor(None, is_admin=True)

    with pytest.raises(ForbiddenError):
        await service.get_entry(nobody)
    with pytest.raises(ForbiddenError):
        await service.upsert_intents(nobody, IntentsUpsert(hiring=True), member_id=BEN)
