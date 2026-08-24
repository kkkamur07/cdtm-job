from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HousingKind(StrEnum):
    OFFER = "offer"
    LOOKING = "looking"


class HousingStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


#: How long a listing stays on the board before the owner has to renew it. Sixty days is
#: longer than most room searches and shorter than the time it takes a listing to go stale.
LISTING_TTL = timedelta(days=60)


class HousingListing(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    member_id: UUID
    kind: HousingKind
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    city: str = Field(min_length=1, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    price_eur: int | None = Field(default=None, ge=0)
    rooms: Decimal | None = Field(default=None, ge=0)
    #: Three states, not two: ``None`` is "the owner did not say", which is why the
    #: filter falls back to the words in the title and description for those listings.
    furnished: bool | None = None
    available_from: date | None = None
    available_until: date | None = None
    photo_urls: list[str] = Field(default_factory=list)
    status: HousingStatus = HousingStatus.OPEN
    #: How many other members have opened the listing. ``None`` for everybody but the
    #: owner and an admin: it is the owner's signal about their own post, not a public
    #: popularity number that would push people towards whatever is already busy.
    view_count: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HousingListingSummary(BaseModel):
    """A listing as the board cards it: the photo, the price, the dates, and no free text.

    The list query selects exactly these columns. ``description`` has no length limit on the
    aggregate and is capped at twenty thousand characters on the way in, so a page of a
    hundred cards used to carry a hundred pages of prose no card draws, read out of the
    database and validated into a full ``HousingListing`` only to be dropped again.

    Restated rather than inherited from ``HousingListing``, because pydantic has no way to
    take a field back off a parent. ``tests/unit/test_list_summary_dtos.py`` pins this field
    set against the aggregate's.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

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
    #: Nulled for everybody but the owner and an admin, exactly as on the aggregate: the
    #: board's list is as much a way of reading a listing as opening one is.
    view_count: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
