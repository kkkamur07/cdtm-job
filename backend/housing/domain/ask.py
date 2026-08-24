"""Ask over the housing board: a plain-words question about rooms, as a filter object.

Same contract as the other boards. A language model may fill in these fields and nothing
else, pydantic decides whether the result is acceptable, and the ordinary repository query
does the rest.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.llm.ask import MAX_ASK_LIMIT, QuestionSource
from backend.housing.domain.housing import HousingKind, HousingListing


class HousingQuery(BaseModel):
    """The strict filter object a housing question is translated into."""

    model_config = ConfigDict(extra="forbid")

    kind: HousingKind | None = Field(
        default=None, description="'offer' for rooms on offer, 'looking' for people searching"
    )
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120, description="a part of the city")
    min_price: int | None = Field(default=None, ge=0, le=100_000, description="euros per month")
    max_price: int | None = Field(default=None, ge=0, le=100_000, description="euros per month")
    available_from: date | None = Field(
        default=None, description="the listing must be free by this date"
    )
    available_until: date | None = Field(
        default=None, description="the listing must still be free on this date"
    )
    min_rooms: float | None = Field(default=None, ge=0, le=20)
    furnished: bool | None = None
    q: str | None = Field(default=None, max_length=200)
    limit: int | None = Field(default=None, ge=1, le=MAX_ASK_LIMIT)

    @field_validator("limit", mode="before")
    @classmethod
    def _clamp_limit(cls, value: object) -> object:
        if isinstance(value, int) and not isinstance(value, bool):
            return max(1, min(value, MAX_ASK_LIMIT))
        return value


class HousingAskInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=300)
    filters: HousingQuery
    confidence: float = Field(ge=0.0, le=1.0)
    unresolved: list[str] = Field(default_factory=list)
    source: QuestionSource


class HousingAskAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpretation: HousingAskInterpretation
    listings: list[HousingListing] = Field(default_factory=list)
    total: int = 0
