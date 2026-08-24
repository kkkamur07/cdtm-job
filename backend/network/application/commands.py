"""Write models for the network context."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.network.domain import IntroStatus


class SaveMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=280)


class IntroRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_member_id: UUID
    message: str = Field(min_length=1, max_length=1000)


class IntroRespond(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IntroStatus
