"""Public response models for the housing API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.llm.ask import MAX_ASK_LIMIT
from backend.housing.domain import HousingAskAnswer, HousingAskInterpretation, HousingListing


class HousingListingPublic(HousingListing):
    """A listing. ``view_count`` is filled in for the owner and an admin, null for others."""

    model_config = ConfigDict(title="HousingListingPublic")


class HousingListingsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[HousingListingPublic]
    total: int


class HousingAskInterpretationPublic(HousingAskInterpretation):
    model_config = ConfigDict(title="HousingAskInterpretationPublic")


class HousingAskAnswerPublic(HousingAskAnswer):
    model_config = ConfigDict(title="HousingAskAnswerPublic")


class HousingAskSchemaPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    json_schema: dict[str, Any]
    kinds: list[str]
    districts: list[str]
    cities: list[str]
    max_limit: int = Field(default=MAX_ASK_LIMIT)
