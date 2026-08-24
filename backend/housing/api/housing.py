from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.core.api.pagination import PageParamsDep
from backend.housing.api.deps import HousingServiceDep
from backend.housing.api.schemas import HousingListingPublic, HousingListingsPublic
from backend.housing.application.commands import HousingCreate, HousingUpdate
from backend.housing.application.ports import HousingFilters
from backend.housing.domain import HousingKind, HousingStatus
from backend.identity.api.deps import ActorDep, MemberActorDep

#: Every read on this board is behind a signed-in Account, the way the members, events and
#: announcements boards are. A Listing names a city, a street, a price and a date somebody's
#: room is free; it is written for other Members, not for the internet.
router = APIRouter(prefix="/housing", tags=["housing"])


@router.get("/", response_model=HousingListingsPublic)
async def list_listings(
    service: HousingServiceDep,
    page: PageParamsDep,
    actor: ActorDep,
    kind: Annotated[HousingKind | None, Query()] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    listing_status: Annotated[HousingStatus | None, Query(alias="status")] = HousingStatus.OPEN,
    member_id: Annotated[UUID | None, Query()] = None,
    furnished: Annotated[bool | None, Query()] = None,
) -> HousingListingsPublic:
    result = await service.list(
        skip=page.skip,
        limit=page.limit,
        filters=HousingFilters(
            kind=kind,
            city=city,
            status=listing_status,
            member_id=member_id,
            furnished=furnished,
            # "My listings" must show the expired ones, or there is nothing to renew.
            include_expired=member_id is not None,
        ),
        actor=actor,
    )
    return HousingListingsPublic(
        items=[HousingListingPublic.model_validate(h) for h in result.items], total=result.total
    )


@router.get("/{listing_id}", response_model=HousingListingPublic)
async def get_listing(
    listing_id: UUID, service: HousingServiceDep, actor: ActorDep
) -> HousingListingPublic:
    """Opening a listing. Counts as a view unless the owner or an admin is the one opening it."""
    return HousingListingPublic.model_validate(await service.view(listing_id, actor))


@router.post("/", response_model=HousingListingPublic, status_code=201)
async def create_listing(
    body: HousingCreate, actor: MemberActorDep, service: HousingServiceDep
) -> HousingListingPublic:
    return HousingListingPublic.model_validate(await service.create(actor, body))


@router.patch("/{listing_id}", response_model=HousingListingPublic)
async def update_listing(
    listing_id: UUID, body: HousingUpdate, actor: MemberActorDep, service: HousingServiceDep
) -> HousingListingPublic:
    return HousingListingPublic.model_validate(await service.update(actor, listing_id, body))


@router.post("/{listing_id}/renew", response_model=HousingListingPublic)
async def renew_listing(
    listing_id: UUID, actor: MemberActorDep, service: HousingServiceDep
) -> HousingListingPublic:
    """Extend the listing by another 60 days from now and reopen it if it was closed."""
    return HousingListingPublic.model_validate(await service.renew(actor, listing_id))


@router.delete("/{listing_id}", status_code=204)
async def delete_listing(
    listing_id: UUID, actor: MemberActorDep, service: HousingServiceDep
) -> Response:
    await service.delete(actor, listing_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
