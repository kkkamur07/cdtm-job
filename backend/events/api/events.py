from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.core.api.pagination import PageParamsDep
from backend.events.api.deps import EventServiceDep
from backend.events.api.schemas import EventPublic, EventsPublic, EventSummaryPublic
from backend.events.application.commands import EventCreate, EventUpdate, RsvpSet
from backend.identity.api.deps import MemberActorDep, OptionalActorDep, PrincipalDep

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=EventsPublic)
async def list_events(
    service: EventServiceDep,
    page: PageParamsDep,
    actor: OptionalActorDep,
    _: PrincipalDep,
    upcoming: Annotated[bool, Query()] = True,
) -> EventsPublic:
    result = await service.list(
        skip=page.skip, limit=page.limit, upcoming_only=upcoming, actor=actor
    )
    return EventsPublic(
        items=[EventSummaryPublic.model_validate(e) for e in result.items], total=result.total
    )


@router.get("/{event_id}", response_model=EventPublic)
async def get_event(
    event_id: UUID, service: EventServiceDep, actor: OptionalActorDep, _: PrincipalDep
) -> EventPublic:
    return EventPublic.model_validate(await service.get(event_id, actor))


@router.post("/", response_model=EventPublic, status_code=201)
async def create_event(
    body: EventCreate, actor: MemberActorDep, service: EventServiceDep
) -> EventPublic:
    return EventPublic.model_validate(await service.create(actor, body))


@router.patch("/{event_id}", response_model=EventPublic)
async def update_event(
    event_id: UUID, body: EventUpdate, actor: MemberActorDep, service: EventServiceDep
) -> EventPublic:
    return EventPublic.model_validate(await service.update(actor, event_id, body))


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: UUID, actor: MemberActorDep, service: EventServiceDep) -> Response:
    await service.delete(actor, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{event_id}/rsvp", response_model=EventPublic)
async def rsvp(
    event_id: UUID, body: RsvpSet, actor: MemberActorDep, service: EventServiceDep
) -> EventPublic:
    return EventPublic.model_validate(await service.rsvp(actor, event_id, body))
