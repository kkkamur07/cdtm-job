"""Public response models for the events API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.events.domain import Event, EventKind, RsvpStatus


class EventPublic(Event):
    model_config = ConfigDict(title="EventPublic")


class EventSummaryPublic(BaseModel):
    """An event as a calendar row: when, where, the counts, and your own answer.

    ``description`` is the only long field on the aggregate and no row draws it, so the
    list leaves it out; ``GET /events/{event_id}`` is where it is read. Copied from
    ``Event`` rather than inherited, because pydantic cannot take a field back off a
    parent. ``tests/unit/test_list_summary_dtos.py`` pins the two field sets together.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True, title="EventSummaryPublic")

    id: UUID
    title: str = Field(min_length=1, max_length=200)
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


class EventsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EventSummaryPublic]
    total: int
