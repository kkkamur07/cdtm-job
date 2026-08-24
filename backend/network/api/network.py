"""Saved people and intro requests.

These used to be ``/community/me/saved`` and ``/community/me/intros``. They are their own
board now: what they are about is the edge between two members, not what one member
maintains about themselves.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import ActorDep, MemberActorDep
from backend.network.api.deps import NetworkServiceDep
from backend.network.api.schemas import (
    IntroRequestPublic,
    IntroRequestsPublic,
    NetworkMemberPublic,
    SavedMemberIdsPublic,
    SavedMemberPublic,
    SavedMembersPublic,
)
from backend.network.application.commands import IntroRequestCreate, IntroRespond, SaveMember
from backend.network.domain import IntroRequest

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/saved", response_model=SavedMembersPublic)
async def my_saved(
    actor: MemberActorDep, service: NetworkServiceDep, page: PageParamsDep
) -> SavedMembersPublic:
    """A shortlist is short, but "short" is not a contract.

    This used to answer a bare list with no skip and no limit, so the size of the body was
    whatever the member had saved. It pages like every other list now, and the skip and the
    limit reach the query rather than the response.
    """
    result = await service.list_saved(actor, skip=page.skip, limit=page.limit)
    return SavedMembersPublic(
        items=[
            SavedMemberPublic(saved=v.saved, member=NetworkMemberPublic.model_validate(v.member))
            for v in result.items
        ],
        total=result.total,
    )


@router.get("/saved/ids", response_model=SavedMemberIdsPublic)
async def my_saved_ids(actor: MemberActorDep, service: NetworkServiceDep) -> SavedMemberIdsPublic:
    """The same shortlist as ``/saved``, as ids, and unpaged on purpose.

    Two questions, two answers. ``/saved`` is what a member reads, so it is a page of cards.
    A Save button asks something else: is this one person on the list, yes or no. Answering
    that from the first page said no about everybody below row one hundred. This is a single
    uuid column bounded by the size of one member's shortlist, so it needs no skip and no
    limit and the client can hold the whole set.
    """
    return SavedMemberIdsPublic(member_ids=await service.saved_ids(actor))


@router.put("/saved/{member_id}", response_model=SavedMemberPublic, status_code=200)
async def save_member(
    member_id: UUID, body: SaveMember, actor: MemberActorDep, service: NetworkServiceDep
) -> SavedMemberPublic:
    """A body without ``note`` saves without touching the note; ``{"note": null}`` clears it."""
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


@router.get("/intros", response_model=IntroRequestsPublic)
async def my_intros(
    actor: MemberActorDep,
    service: NetworkServiceDep,
    page: PageParamsDep,
    with_member_id: Annotated[
        UUID | None,
        Query(description="only requests whose other party is this member, either direction"),
    ] = None,
) -> IntroRequestsPublic:
    """Both directions, paged. Unbounded before, for the same reason ``/saved`` was.

    ``with_member_id`` is how a profile page asks "have I already asked for an intro to this
    person": one row or none, instead of the whole history filtered in the browser.
    """
    result = await service.list_intros(
        actor, skip=page.skip, limit=page.limit, with_member_id=with_member_id
    )
    return IntroRequestsPublic(
        items=[
            IntroRequestPublic(
                request=v.request,
                requester=NetworkMemberPublic.model_validate(v.requester),
                target=NetworkMemberPublic.model_validate(v.target),
            )
            for v in result.items
        ],
        total=result.total,
    )


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
