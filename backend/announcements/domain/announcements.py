from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Announcement(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    author_member_id: UUID | None = None
    is_pinned: bool = False
    published_at: datetime | None = None
    expires_at: datetime | None = None
    read_count: int = 0
    is_read: bool = False
    created_at: datetime
    updated_at: datetime
