"""Write models for the events context."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.core.text import MAX_RICH_TEXT
from backend.events.domain import EventKind, RsvpStatus


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    kind: EventKind = EventKind.COMMUNITY
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    url: str | None = None
    is_published: bool = True


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    kind: EventKind | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    url: str | None = None
    is_published: bool | None = None


class RsvpSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RsvpStatus | None = Field(default=None, description="null clears the RSVP")
