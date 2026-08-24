"""Write models for the housing context."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backend.core.text import MAX_RICH_TEXT
from backend.housing.domain import HousingKind, HousingStatus


class HousingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: HousingKind
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    city: str = Field(min_length=1, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    price_eur: int | None = Field(default=None, ge=0)
    rooms: Decimal | None = Field(default=None, ge=0)
    #: Left unset means "did not say", which the board and Ask both treat as unknown.
    furnished: bool | None = None
    available_from: date | None = None
    available_until: date | None = None
    photo_urls: list[str] = Field(default_factory=list, max_length=10)


class HousingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    price_eur: int | None = Field(default=None, ge=0)
    rooms: Decimal | None = Field(default=None, ge=0)
    furnished: bool | None = None
    available_from: date | None = None
    available_until: date | None = None
    photo_urls: list[str] | None = Field(default=None, max_length=10)
    status: HousingStatus | None = None
