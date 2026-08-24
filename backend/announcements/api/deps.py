"""Wiring for the announcements context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.announcements.application.announcement_service import AnnouncementService
from backend.announcements.infrastructure.announcements_repository import (
    SqlAnnouncementRepository,
)
from backend.identity.api.deps import DbDep


def get_announcement_service(db: DbDep) -> AnnouncementService:
    return AnnouncementService(SqlAnnouncementRepository(db))


AnnouncementServiceDep = Annotated[AnnouncementService, Depends(get_announcement_service)]
