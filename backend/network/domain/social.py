"""Network: saved people and intro requests."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SavedMember(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    owner_member_id: UUID
    saved_member_id: UUID
    note: str | None = Field(default=None, max_length=280)
    created_at: datetime | None = None


class IntroStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class IntroRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    requester_member_id: UUID
    target_member_id: UUID
    message: str = Field(min_length=1, max_length=1000)
    status: IntroStatus = IntroStatus.PENDING
    created_at: datetime
    responded_at: datetime | None = None
