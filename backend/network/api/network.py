"""Saved people and intro requests.

These used to be ``/community/me/saved`` and ``/community/me/intros``. They are their own
board now: what they are about is the edge between two members, not what one member
maintains about themselves.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response, status

from backend.identity.api.deps import ActorDep, MemberActorDep
from backend.network.api.deps import NetworkServiceDep
from backend.network.api.schemas import (
    IntroRequestPublic,
    NetworkMemberPublic,
    SavedMemberPublic,
)
from backend.network.application.commands import IntroRequestCreate, IntroRespond, SaveMember
from backend.network.domain import IntroRequest

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/saved", response_model=list[SavedMemberPublic])
async def my_saved(actor: MemberActorDep, service: NetworkServiceDep) -> list[SavedMemberPublic]:
    return [
        SavedMemberPublic(saved=v.saved, member=NetworkMemberPublic.model_validate(v.member))
        for v in await service.list_saved(actor)
    ]


@router.put("/saved/{member_id}", response_model=SavedMemberPublic, status_code=200)
async def save_member(
    member_id: UUID, body: SaveMember, actor: MemberActorDep, service: NetworkServiceDep
) -> SavedMemberPublic:
    view = await service.save(actor, member_id, body)
    return SavedMemberPublic(
        saved=view.saved, member=NetworkMemberPublic.model_validate(view.member)
    )


@router.delete("/saved/{member_id}", status_code=204)
async def unsave_member(
    member_id: UUID, actor: MemberActorDep, service: NetworkServiceDep
) -> Response:
    await service.unsave(actor, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/intros", response_model=list[IntroRequestPublic])
async def my_intros(actor: MemberActorDep, service: NetworkServiceDep) -> list[IntroRequestPublic]:
    return [
        IntroRequestPublic(
            request=v.request,
            requester=NetworkMemberPublic.model_validate(v.requester),
            target=NetworkMemberPublic.model_validate(v.target),
        )
        for v in await service.list_intros(actor)
    ]


@router.post("/intros", response_model=IntroRequest, status_code=201)
async def request_intro(
    body: IntroRequestCreate, actor: MemberActorDep, service: NetworkServiceDep
) -> IntroRequest:
    return await service.request_intro(actor, body)


@router.post("/intros/{request_id}/respond", response_model=IntroRequest)
async def respond_intro(
    request_id: UUID, body: IntroRespond, actor: ActorDep, service: NetworkServiceDep
) -> IntroRequest:
    return await service.respond_intro(actor, request_id, body)
