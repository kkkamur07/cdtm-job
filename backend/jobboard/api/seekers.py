from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response, status

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import ActorDep, PrincipalDep
from backend.jobboard.api.deps import SeekerServiceDep
from backend.jobboard.api.schemas import SeekerPublic, SeekersPublic
from backend.jobboard.application.commands import SeekerCreate, SeekerUpdate

router = APIRouter(prefix="/seekers", tags=["seekers"])


@router.get("/", response_model=SeekersPublic)
async def list_seekers(
    service: SeekerServiceDep, page: PageParamsDep, actor: ActorDep
) -> SeekersPublic:
    """Contact details are hidden from everybody but the seeker themselves and an admin."""
    result = await service.list_seekers(skip=page.skip, limit=page.limit, actor=actor)
    return SeekersPublic(
        items=[SeekerPublic.model_validate(s) for s in result.items], total=result.total
    )


@router.get("/{seeker_id}", response_model=SeekerPublic)
async def get_seeker(service: SeekerServiceDep, seeker_id: UUID, actor: ActorDep) -> SeekerPublic:
    return SeekerPublic.model_validate(await service.get_seeker(seeker_id, actor))


@router.post("/", response_model=SeekerPublic, status_code=201)
async def create_seeker(
    service: SeekerServiceDep, body: SeekerCreate, principal: PrincipalDep
) -> SeekerPublic:
    return SeekerPublic.model_validate(
        await service.create_seeker(body, member_id=principal.member_id)
    )


@router.patch("/{seeker_id}", response_model=SeekerPublic)
async def update_seeker(
    service: SeekerServiceDep, seeker_id: UUID, body: SeekerUpdate, actor: ActorDep
) -> SeekerPublic:
    return SeekerPublic.model_validate(await service.update_seeker(actor, seeker_id, body))


@router.delete("/{seeker_id}", status_code=204)
async def delete_seeker(service: SeekerServiceDep, seeker_id: UUID, actor: ActorDep) -> Response:
    await service.delete_seeker(actor, seeker_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
