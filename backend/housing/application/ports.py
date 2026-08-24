"""Persistence and translation ports for the housing context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from backend.core.llm.ask import ViewerContext
from backend.core.page import PageResult
from backend.housing.application.commands import HousingCreate, HousingUpdate
from backend.housing.domain import (
    HousingAskInterpretation,
    HousingKind,
    HousingListing,
    HousingListingSummary,
    HousingStatus,
)


@dataclass(frozen=True, slots=True)
class HousingFilters:
    kind: HousingKind | None = None
    city: str | None = None
    district: str | None = None
    status: HousingStatus | None = None
    member_id: UUID | None = None
    min_price: int | None = None
    max_price: int | None = None
    available_from: date | None = None
    available_until: date | None = None
    min_rooms: float | None = None
    furnished: bool | None = None
    q: str | None = None
    #: Expired listings stay out of the board. Owners (member_id filter) still see theirs.
    include_expired: bool = False


class HousingRepository(Protocol):
    #: The list hands back cards, not listings: it is the only read that returns many rows at
    #: once, and the aggregate's ``description`` is the one field no card draws. ``get`` and
    #: every write still answer with the whole aggregate.
    async def list(
        self, *, skip: int, limit: int, filters: HousingFilters
    ) -> PageResult[HousingListingSummary]: ...
    async def get(self, listing_id: UUID) -> HousingListing | None: ...
    async def create(
        self, member_id: UUID, payload: HousingCreate, *, expires_at: datetime
    ) -> HousingListing: ...
    async def update(self, listing_id: UUID, payload: HousingUpdate) -> HousingListing | None: ...
    async def renew(self, listing_id: UUID, *, expires_at: datetime) -> HousingListing | None: ...
    async def delete(self, listing_id: UUID) -> bool: ...
    async def record_view(self, listing_id: UUID) -> None: ...


class HousingQueryTranslator(Protocol):
    model_name: str

    async def translate(
        self, question: str, *, viewer: ViewerContext
    ) -> HousingAskInterpretation: ...
