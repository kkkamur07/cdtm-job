"""Entry and Intents: what a member maintains about themselves, and who may edit it."""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.members.application.commands import (
    EntryUpsert,
    IntentsUpsert,
)
from backend.members.application.ports import (
    EntryRepository,
    MemberRepository,
)
from backend.members.domain import (
    MemberEntry,
    MemberIntents,
)


class EntryService:
    """A member edits their own Entry and Intents; admins may edit anyone's."""

    def __init__(self, entries: EntryRepository, members: MemberRepository) -> None:
        self._entries = entries
        self._members = members

    async def _target(self, actor: Actor, member_id: UUID | None) -> UUID:
        own = actor.require_member()
        if member_id is None or member_id == own:
            return own
        if not actor.is_admin:
            raise ForbiddenError("you can only edit your own entry")
        if await self._members.get_by_id(member_id) is None:
            raise NotFoundError("member not found")
        return member_id

    async def get_entry(self, actor: Actor, member_id: UUID | None = None) -> MemberEntry | None:
        return await self._entries.get(await self._target(actor, member_id))

    async def upsert_entry(
        self, actor: Actor, payload: EntryUpsert, member_id: UUID | None = None
    ) -> MemberEntry:
        return await self._entries.upsert(await self._target(actor, member_id), payload)

    async def get_intents(
        self, actor: Actor, member_id: UUID | None = None
    ) -> MemberIntents | None:
        return await self._entries.get_intents(await self._target(actor, member_id))

    async def upsert_intents(
        self, actor: Actor, payload: IntentsUpsert, member_id: UUID | None = None
    ) -> MemberIntents:
        return await self._entries.upsert_intents(await self._target(actor, member_id), payload)
