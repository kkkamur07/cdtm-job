"""Persistence ports for the events context."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.core.page import PageResult
from backend.events.application.commands import EventCreate, EventUpdate
from backend.events.domain import Event, EventSummary, RsvpStatus


class EventRepository(Protocol):
    #: The list hands back rows, not events: it is the only read that returns many at once,
    #: and ``description`` is the one field on the aggregate no calendar row draws. ``get``
    #: and every write still answer with the whole aggregate.
    async def list(
        self, *, skip: int, limit: int, upcoming_only: bool, viewer_member_id: UUID | None
    ) -> PageResult[EventSummary]: ...
    async def get(self, event_id: UUID, viewer_member_id: UUID | None) -> Event | None: ...
    async def create(self, payload: EventCreate, created_by_member_id: UUID | None) -> Event: ...
    async def update(self, event_id: UUID, payload: EventUpdate) -> Event | None: ...
    async def delete(self, event_id: UUID) -> bool: ...
    async def set_rsvp(
        self, event_id: UUID, member_id: UUID, status: RsvpStatus | None
    ) -> None: ...
