"""Events: who may publish one, who may edit it, and what an RSVP does."""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult
from backend.events.application.commands import (
    EventCreate,
    EventUpdate,
    RsvpSet,
)
from backend.events.application.ports import (
    EventRepository,
)
from backend.events.domain import (
    Event,
    EventSummary,
)


def _is_organiser(event: Event, actor: Actor | None) -> bool:
    """Both sides are nullable, so an unbound Account must never match an authorless row."""
    if actor is None or actor.member_id is None:
        return False
    return event.created_by_member_id == actor.member_id


def _is_visible(event: Event, actor: Actor | None) -> bool:
    if event.is_published:
        return True
    return _is_organiser(event, actor) or bool(actor and actor.is_admin)


class EventService:
    def __init__(self, events: EventRepository) -> None:
        self._events = events

    async def list(
        self, *, skip: int, limit: int, upcoming_only: bool, actor: Actor | None
    ) -> PageResult[EventSummary]:
        """A page of calendar rows. ``get`` is where an event is read whole."""
        return await self._events.list(
            skip=skip,
            limit=limit,
            upcoming_only=upcoming_only,
            viewer_member_id=actor.member_id if actor else None,
        )

    async def get(self, event_id: UUID, actor: Actor | None) -> Event:
        """An unpublished event is not on the board and is not fetchable by id either.

        Absent rather than forbidden: an event nobody has decided to announce yet is not
        something a caller may confirm the existence of, and ``rsvp`` goes through here, so
        this is also what stops anyone RSVPing to one.
        """
        ev = await self._events.get(event_id, actor.member_id if actor else None)
        if ev is None or not _is_visible(ev, actor):
            raise NotFoundError("event not found")
        return ev

    async def create(self, actor: Actor, payload: EventCreate) -> Event:
        return await self._events.create(payload, actor.require_member())

    async def update(self, actor: Actor, event_id: UUID, payload: EventUpdate) -> Event:
        ev = await self.get(event_id, actor)
        if not _is_organiser(ev, actor) and not actor.is_admin:
            raise ForbiddenError("only the organiser or an admin can edit this event")
        updated = await self._events.update(event_id, payload)
        if updated is None:
            raise NotFoundError("event not found")
        return updated

    async def delete(self, actor: Actor, event_id: UUID) -> None:
        ev = await self.get(event_id, actor)
        if not _is_organiser(ev, actor) and not actor.is_admin:
            raise ForbiddenError("only the organiser or an admin can delete this event")
        await self._events.delete(event_id)

    async def rsvp(self, actor: Actor, event_id: UUID, payload: RsvpSet) -> Event:
        member_id = actor.require_member()
        await self.get(event_id, actor)
        await self._events.set_rsvp(event_id, member_id, payload.status)
        return await self.get(event_id, actor)
