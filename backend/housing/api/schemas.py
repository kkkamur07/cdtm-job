"""Public response models for the housing API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.core.llm.ask import MAX_ASK_LIMIT
from backend.housing.domain import (
    HousingAskAnswer,
    HousingAskInterpretation,
    HousingKind,
    HousingListing,
    HousingStatus,
)


class HousingListingPublic(HousingListing):
    """A listing. ``view_count`` is filled in for the owner and an admin, null for others."""

    model_config = ConfigDict(title="HousingListingPublic")


class HousingListingSummaryPublic(BaseModel):
    """A listing as a board card: the photo, the price, the dates, and no free text.

    ``description`` has no length limit on the aggregate and is capped at twenty thousand
    characters on the way in, so a hundred listings carried a page of prose per card that
    the card never draws. Opening a listing answers with ``HousingListingPublic``, which is
    where the description is read.

    Copied from ``HousingListing`` rather than inherited: pydantic cannot take a field back
    off a parent. ``tests/unit/test_list_summary_dtos.py`` pins the two field sets together.
    """

    model_config = ConfigDict(
        extra="forbid", from_attributes=True, title="HousingListingSummaryPublic"
    )

    id: UUID
    member_id: UUID
    kind: HousingKind
    title: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    price_eur: int | None = Field(default=None, ge=0)
    rooms: Decimal | None = Field(default=None, ge=0)
    furnished: bool | None = None
    available_from: date | None = None
    available_until: date | None = None
    photo_urls: list[str] = Field(default_factory=list)
    status: HousingStatus = HousingStatus.OPEN
    view_count: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HousingListingsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[HousingListingSummaryPublic]
    total: int


class HousingAskInterpretationPublic(HousingAskInterpretation):
    #: ``from_attributes`` so the router can validate the domain object itself instead of
    #: dumping it to a dict first and validating that.
    model_config = ConfigDict(from_attributes=True, title="HousingAskInterpretationPublic")


class HousingAskAnswerPublic(HousingAskAnswer):
    """An answer is a list of cards, so it ships the same summary the board does."""

    model_config = ConfigDict(from_attributes=True, title="HousingAskAnswerPublic")

    listings: list[HousingListingSummaryPublic] = Field(default_factory=list)


class HousingAskSchemaPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    json_schema: dict[str, Any]
    kinds: list[str]
    districts: list[str]
    cities: list[str]
    max_limit: int = Field(default=MAX_ASK_LIMIT)
