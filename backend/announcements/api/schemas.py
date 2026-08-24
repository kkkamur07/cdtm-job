"""Public response models for the announcements API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.announcements.domain import Announcement


class AnnouncementPublic(Announcement):
    model_config = ConfigDict(title="AnnouncementPublic")


class AnnouncementsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AnnouncementPublic]
    total: int
    unread: int


class UnreadCountPublic(BaseModel):
    """Just the badge. The header needs the number without the first page of the board."""

    model_config = ConfigDict(extra="forbid", title="UnreadCountPublic")

    unread: int
