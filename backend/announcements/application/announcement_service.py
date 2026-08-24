"""Announcements: admins publish, members read, and a read is recorded once."""

from __future__ import annotations

from uuid import UUID

from backend.announcements.application.commands import (
    AnnouncementCreate,
    AnnouncementUpdate,
)
from backend.announcements.application.ports import (
    AnnouncementRepository,
)
from backend.announcements.domain import (
    Announcement,
)
from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult


class AnnouncementService:
    def __init__(self, announcements: AnnouncementRepository) -> None:
        self._ann = announcements

    async def list(self, *, skip: int, limit: int, actor: Actor | None) -> PageResult[Announcement]:
        return await self._ann.list(
            skip=skip,
            limit=limit,
            viewer_member_id=actor.member_id if actor else None,
            include_unpublished=bool(actor and actor.is_admin),
        )

    async def get(self, announcement_id: UUID, actor: Actor | None) -> Announcement:
        """Only what is on the board right now, unless an admin is asking.

        The board hides three kinds of row: never published, published in the future, and
        already expired. The list endpoint has always hidden all three; fetching one by id
        hid only the first, so an expired announcement stayed readable by anybody who kept
        the link.
        """
        is_admin = bool(actor and actor.is_admin)
        a = await self._ann.get(
            announcement_id, actor.member_id if actor else None, include_hidden=is_admin
        )
        if a is None:
            raise NotFoundError("announcement not found")
        return a

    async def create(self, actor: Actor, payload: AnnouncementCreate) -> Announcement:
        if not actor.is_admin:
            raise ForbiddenError("admin only")
        return await self._ann.create(payload, actor.member_id)

    async def update(
        self, actor: Actor, announcement_id: UUID, payload: AnnouncementUpdate
    ) -> Announcement:
        if not actor.is_admin:
            raise ForbiddenError("admin only")
        a = await self._ann.update(announcement_id, payload)
        if a is None:
            raise NotFoundError("announcement not found")
        return a

    async def delete(self, actor: Actor, announcement_id: UUID) -> None:
        if not actor.is_admin:
            raise ForbiddenError("admin only")
        if not await self._ann.delete(announcement_id):
            raise NotFoundError("announcement not found")

    async def mark_read(self, actor: Actor, announcement_id: UUID) -> Announcement:
        member_id = actor.require_member()
        await self.get(announcement_id, actor)
        await self._ann.mark_read(announcement_id, member_id)
        return await self.get(announcement_id, actor)

    async def unread_count(self, actor: Actor) -> int:
        if actor.member_id is None:
            return 0
        return await self._ann.unread_count(actor.member_id)
