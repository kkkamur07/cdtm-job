from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventKind(StrEnum):
    CDTM = "cdtm"
    COMMUNITY = "community"
    EXTERNAL = "external"


class RsvpStatus(StrEnum):
    GOING = "going"
    INTERESTED = "interested"
    DECLINED = "declined"


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    kind: EventKind = EventKind.COMMUNITY
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    url: str | None = None
    created_by_member_id: UUID | None = None
    is_published: bool = True
    going_count: int = 0
    interested_count: int = 0
    my_rsvp: RsvpStatus | None = None
    created_at: datetime
    updated_at: datetime


class Rsvp(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    event_id: UUID
    member_id: UUID
    status: RsvpStatus
    created_at: datetime | None = None
