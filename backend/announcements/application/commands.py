"""Write models for the announcements context."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.core.text import MAX_RICH_TEXT


class AnnouncementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=MAX_RICH_TEXT)
    is_pinned: bool = False
    published_at: datetime | None = None
    expires_at: datetime | None = None


class AnnouncementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=MAX_RICH_TEXT)
    is_pinned: bool | None = None
    published_at: datetime | None = None
    expires_at: datetime | None = None
