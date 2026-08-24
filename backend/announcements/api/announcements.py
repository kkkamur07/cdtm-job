from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response, status

from backend.announcements.api.deps import AnnouncementServiceDep
from backend.announcements.api.schemas import AnnouncementPublic, AnnouncementsPublic
from backend.announcements.application.commands import AnnouncementCreate, AnnouncementUpdate
from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import (
    ActorDep,
    MemberActorDep,
    OptionalActorDep,
    PrincipalDep,
)

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/", response_model=AnnouncementsPublic)
async def list_announcements(
    service: AnnouncementServiceDep, page: PageParamsDep, actor: OptionalActorDep, _: PrincipalDep
) -> AnnouncementsPublic:
    result = await service.list(skip=page.skip, limit=page.limit, actor=actor)
    unread = await service.unread_count(actor) if actor else 0
    return AnnouncementsPublic(
        items=[AnnouncementPublic.model_validate(a) for a in result.items],
        total=result.total,
        unread=unread,
    )


@router.get("/{announcement_id}", response_model=AnnouncementPublic)
async def get_announcement(
    announcement_id: UUID, service: AnnouncementServiceDep, actor: OptionalActorDep, _: PrincipalDep
) -> AnnouncementPublic:
    return AnnouncementPublic.model_validate(await service.get(announcement_id, actor))


@router.post("/", response_model=AnnouncementPublic, status_code=201)
async def create_announcement(
    body: AnnouncementCreate, actor: ActorDep, service: AnnouncementServiceDep
) -> AnnouncementPublic:
    return AnnouncementPublic.model_validate(await service.create(actor, body))


@router.patch("/{announcement_id}", response_model=AnnouncementPublic)
async def update_announcement(
    announcement_id: UUID,
    body: AnnouncementUpdate,
    actor: ActorDep,
    service: AnnouncementServiceDep,
) -> AnnouncementPublic:
    return AnnouncementPublic.model_validate(await service.update(actor, announcement_id, body))


@router.delete("/{announcement_id}", status_code=204)
async def delete_announcement(
    announcement_id: UUID, actor: ActorDep, service: AnnouncementServiceDep
) -> Response:
    await service.delete(actor, announcement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{announcement_id}/read", response_model=AnnouncementPublic)
async def mark_read(
    announcement_id: UUID, actor: MemberActorDep, service: AnnouncementServiceDep
) -> AnnouncementPublic:
    return AnnouncementPublic.model_validate(await service.mark_read(actor, announcement_id))
