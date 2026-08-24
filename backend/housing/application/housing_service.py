"""Listings: who may edit one, when it expires, and what renewing does."""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult
from backend.housing.application.commands import HousingCreate, HousingUpdate
from backend.housing.application.ports import HousingFilters, HousingRepository
from backend.housing.application.visibility import (
    for_viewer,
    is_on_the_board,
    is_owner,
    sanitized_list_filters,
)
from backend.housing.domain import LISTING_TTL, HousingListing
from infrastructure.repository import utc_now


class HousingService:
    def __init__(self, housing: HousingRepository) -> None:
        self._housing = housing

    async def list(
        self, *, skip: int, limit: int, filters: HousingFilters, actor: Actor | None = None
    ) -> PageResult[HousingListing]:
        filters = sanitized_list_filters(filters, actor)
        result = await self._housing.list(skip=skip, limit=limit, filters=filters)
        return PageResult(items=[for_viewer(r, actor) for r in result.items], total=result.total)

    async def get(self, listing_id: UUID) -> HousingListing:
        """The listing as stored. Use :meth:`view` for anything a member is shown."""
        row = await self._housing.get(listing_id)
        if row is None:
            raise NotFoundError("listing not found")
        return row

    async def view(self, listing_id: UUID, actor: Actor | None) -> HousingListing:
        """One member opening one listing.

        The counter is what tells an owner whether renewing is worth it, so it counts other
        people looking and not the owner refreshing their own page. Admins are not counted
        either: they open listings to moderate them.
        """
        row = await self.get(listing_id)
        if not is_on_the_board(row, actor):
            # Off the board is off the board: a closed or expired listing is not fetchable
            # by id either, or a stale link keeps answering long after the room went.
            raise NotFoundError("listing not found")
        owner = is_owner(row, actor)
        if actor is not None and not owner and not actor.is_admin:
            await self._housing.record_view(listing_id)
            row = row.model_copy(update={"view_count": row.view_count + 1})
        return for_viewer(row, actor)

    async def create(self, actor: Actor, payload: HousingCreate) -> HousingListing:
        return await self._housing.create(
            actor.require_member(), payload, expires_at=utc_now() + LISTING_TTL
        )

    async def renew(self, actor: Actor, listing_id: UUID) -> HousingListing:
        """Push the expiry out by one TTL from now and reopen the listing."""
        row = await self.get(listing_id)
        if not is_owner(row, actor) and not actor.is_admin:
            raise ForbiddenError("only the owner or an admin can renew this listing")
        renewed = await self._housing.renew(listing_id, expires_at=utc_now() + LISTING_TTL)
        if renewed is None:
            raise NotFoundError("listing not found")
        return renewed

    async def update(
        self, actor: Actor, listing_id: UUID, payload: HousingUpdate
    ) -> HousingListing:
        row = await self.get(listing_id)
        if not is_owner(row, actor) and not actor.is_admin:
            raise ForbiddenError("only the owner or an admin can edit this listing")
        updated = await self._housing.update(listing_id, payload)
        if updated is None:
            raise NotFoundError("listing not found")
        return updated

    async def delete(self, actor: Actor, listing_id: UUID) -> None:
        row = await self.get(listing_id)
        if not is_owner(row, actor) and not actor.is_admin:
            raise ForbiddenError("only the owner or an admin can delete this listing")
        await self._housing.delete(listing_id)
