"""What a PUT to ``/network/saved/{id}`` does to a note the member already wrote.

``note`` is nullable, so ``None`` arrives from two different requests: the Save button on a
card, which has no note to send and must not destroy one, and a member emptying the box,
which must. Only ``model_fields_set`` tells them apart, and that distinction lives in the
service. A fake repository records what it was asked for; nothing here touches a database.
"""

from __future__ import annotations

import uuid

from backend.core.actor import Actor
from backend.network.application.commands import SaveMember
from backend.network.application.network_service import NetworkService
from backend.network.domain import MemberCard, SavedMember

OWNER = uuid.uuid4()
SAVED = uuid.uuid4()


class Directory:
    async def exists(self, member_id: uuid.UUID) -> bool:
        return True

    async def cards(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, MemberCard]:
        return {i: MemberCard(id=i, slug="somebody", name="Somebody") for i in ids}


class RecordingNetwork:
    """``save`` and ``saved_ids``, remembering the arguments they were handed."""

    def __init__(self, ids: list[uuid.UUID] | None = None) -> None:
        self.calls: list[tuple[str | None, bool]] = []
        self.owners: list[uuid.UUID] = []
        self._ids = ids or []

    async def save(
        self,
        owner_member_id: uuid.UUID,
        saved_member_id: uuid.UUID,
        note: str | None,
        *,
        replace_note: bool,
    ) -> SavedMember:
        self.calls.append((note, replace_note))
        return SavedMember(
            owner_member_id=owner_member_id, saved_member_id=saved_member_id, note=note
        )

    async def saved_ids(self, owner_member_id: uuid.UUID) -> list[uuid.UUID]:
        self.owners.append(owner_member_id)
        return list(self._ids)


async def test_a_body_without_a_note_leaves_the_stored_one_alone() -> None:
    """The Save button sends ``{}``; the note the member wrote yesterday survives it."""
    network = RecordingNetwork()
    service = NetworkService(network, Directory())

    await service.save(Actor(OWNER), SAVED, SaveMember())

    assert network.calls == [(None, False)]


async def test_an_explicit_null_note_clears_it() -> None:
    """Same value, opposite intent: the field was sent, so the write goes through."""
    network = RecordingNetwork()
    service = NetworkService(network, Directory())

    await service.save(Actor(OWNER), SAVED, SaveMember.model_validate({"note": None}))

    assert network.calls == [(None, True)]


async def test_a_note_with_text_is_written() -> None:
    network = RecordingNetwork()
    service = NetworkService(network, Directory())

    view = await service.save(Actor(OWNER), SAVED, SaveMember(note="ask about VC"))

    assert network.calls == [("ask about VC", True)]
    assert view.saved.note == "ask about VC"


async def test_saved_ids_asks_only_about_the_acting_member() -> None:
    ids = [uuid.uuid4(), uuid.uuid4()]
    network = RecordingNetwork(ids)

    assert await NetworkService(network, Directory()).saved_ids(Actor(OWNER)) == ids
    assert network.owners == [OWNER]
