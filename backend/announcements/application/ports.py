"""Persistence ports for the announcements context."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.announcements.application.commands import AnnouncementCreate, AnnouncementUpdate
from backend.announcements.domain import Announcement
from backend.core.page import PageResult


class AnnouncementRepository(Protocol):
    async def list(
        self, *, skip: int, limit: int, viewer_member_id: UUID | None, include_unpublished: bool
    ) -> PageResult[Announcement]: ...
    async def get(
        self, announcement_id: UUID, viewer_member_id: UUID | None, *, include_hidden: bool = False
    ) -> Announcement | None: ...
    async def create(
        self, payload: AnnouncementCreate, author_member_id: UUID | None
    ) -> Announcement: ...
    async def update(
        self, announcement_id: UUID, payload: AnnouncementUpdate
    ) -> Announcement | None: ...
    async def delete(self, announcement_id: UUID) -> bool: ...
    async def mark_read(self, announcement_id: UUID, member_id: UUID) -> None: ...
    async def unread_count(self, member_id: UUID) -> int: ...
