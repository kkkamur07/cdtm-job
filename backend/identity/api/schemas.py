from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.identity.domain import Account


class AccountPublic(Account):
    model_config = ConfigDict(title="AccountPublic")


class AccountsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AccountPublic]
    total: int


class MePublic(BaseModel):
    """Who am I: the account plus whether it is linked to a member."""

    account: AccountPublic
    member_id: UUID | None
    member_slug: str | None
    is_admin: bool


class BindMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_slug: str = Field(min_length=1, max_length=128)


class SetAdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_admin: bool


class DevLoginRequest(BaseModel):
    """Body of the development-only sign-in. Absent from the schema in production.

    ``member_slug`` is the identifier: it names the Member to sign in as, and the address is
    read from that roster row (or written onto it when the row has none). ``email`` is kept
    only so the frontend can catch up, and should be dropped once it posts ``member_slug``;
    passing both still works and still 409s when they disagree.
    """

    model_config = ConfigDict(extra="forbid")

    member_slug: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(
        default=None,
        min_length=3,
        max_length=255,
        description=(
            "Deprecated, kept for one transition while the frontend switches to member_slug. "
            "Pass member_slug instead; passing both 409s if they name different people."
        ),
    )

    @model_validator(mode="after")
    def _one_identifier(self) -> DevLoginRequest:
        if not self.member_slug and not self.email:
            raise ValueError("pass member_slug (or, for now, email)")
        return self


class DevLoginResponse(BaseModel):
    """Shaped like an OAuth token response so the frontend stores it the way it will store
    a Supabase session."""

    access_token: str
    # noqa: S105 is a false positive; "bearer" is the OAuth token *type*, not a credential.
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    me: MePublic


class DevMemberOption(BaseModel):
    """One entry in the impersonation picker.

    Deliberately not a :class:`MemberSummary`: this route is unauthenticated, because the
    picker is what a developer uses before they have a token, and a list of real names with
    real Workspace addresses next to them is a mailing list anyone who can reach the port can
    take. The slug is the identifier ``POST /auth/dev/login`` wants, so the address does not
    need to travel at all.
    """

    model_config = ConfigDict(extra="forbid", title="DevMemberOption")

    id: UUID
    slug: str
    name: str
    class_label: str | None = None
