"""Entry: what a member maintains about themselves on top of the scrape."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContactPreference(StrEnum):
    EMAIL = "email"
    INTRO = "intro"
    LINKEDIN = "linkedin"


class Visibility(StrEnum):
    MEMBERS = "members"
    HIDDEN = "hidden"


class MemberIntents(BaseModel):
    """What a member is open to. Drives intent-aware search."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    cofounding: bool = False
    mentoring: bool = False
    hiring: bool = False
    open_to_roles: bool = False
    speaking: bool = False
    investing: bool = False
    note: str | None = Field(default=None, max_length=280)
    updated_at: datetime | None = None

    @property
    def any(self) -> bool:
        return any(
            (
                self.cofounding,
                self.mentoring,
                self.hiring,
                self.open_to_roles,
                self.speaking,
                self.investing,
            )
        )


class MemberEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    member_id: UUID
    ask_me_about: str | None = Field(default=None, max_length=500)
    about: str | None = Field(default=None, max_length=2000)
    current_title: str | None = Field(default=None, max_length=160)
    current_company: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    contact_preference: ContactPreference = ContactPreference.INTRO
    contact_email: str | None = Field(default=None, max_length=255)
    hobbies: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    visibility: Visibility = Visibility.MEMBERS
    created_at: datetime | None = None
    updated_at: datetime | None = None
