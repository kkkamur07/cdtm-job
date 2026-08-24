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


class EventSummary(BaseModel):
    """An event as the calendar rows it: when, where, the counts, and your own answer.

    The list query selects exactly these columns plus the three counted ones.
    ``description`` is the only long field on the aggregate and no row draws it, so the list
    leaves it out; ``GET /events/{event_id}`` is where it is read.

    Restated rather than inherited from ``Event``, because pydantic has no way to take a
    field back off a parent. ``tests/unit/test_list_summary_dtos.py`` pins this field set
    against the aggregate's.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    title: str = Field(min_length=1, max_length=200)
    kind: EventKind = EventKind.COMMUNITY
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    url: str | None = None
    created_by_member_id: UUID | None = None
    is_published: bool = True
    #: Counted per row by the query, not stored: they are correlated subqueries over the
    #: RSVP table, the same three the detail read uses.
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
