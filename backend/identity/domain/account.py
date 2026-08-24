from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TokenClaims(BaseModel):
    """The subset of a Supabase access token the app relies on."""

    model_config = ConfigDict(extra="ignore")

    sub: UUID
    email: str
    #: False unless the token said so. A claim nobody made is not a claim of verification.
    email_verified: bool = False
    full_name: str | None = None
    avatar_url: str | None = None
    provider: str | None = None


class Account(BaseModel):
    """A login identity. One Account binds to at most one Member."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    auth_user_id: UUID
    email: str = Field(max_length=255)
    full_name: str | None = None
    avatar_url: str | None = None
    member_id: UUID | None = None
    is_admin: bool = False
    last_sign_in_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class Principal(BaseModel):
    """The authenticated caller for one request."""

    model_config = ConfigDict(extra="forbid")

    account: Account

    @property
    def member_id(self) -> UUID | None:
        return self.account.member_id

    @property
    def is_admin(self) -> bool:
        return self.account.is_admin

    @property
    def email(self) -> str:
        return self.account.email
