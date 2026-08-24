from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.core.page import PageResult
from backend.identity.domain import Account, MemberSummary, TokenClaims


class TokenVerifier(Protocol):
    def verify(self, token: str) -> TokenClaims:
        """Return claims for a valid token or raise ``UnauthorizedError``."""
        ...


class AccountRepository(Protocol):
    async def get_by_auth_user_id(self, auth_user_id: UUID) -> Account | None: ...
    async def get_by_id(self, account_id: UUID) -> Account | None: ...
    async def list_accounts(
        self, *, skip: int, limit: int, unbound_only: bool
    ) -> PageResult[Account]: ...
    async def upsert_from_claims(
        self, claims: TokenClaims, *, is_admin: bool | None
    ) -> Account: ...
    async def bind_member(self, account_id: UUID, member_id: UUID) -> Account: ...
    async def set_admin(self, account_id: UUID, is_admin: bool) -> Account: ...


class MemberDirectory(Protocol):
    """Read-only view into the community context, used only to bind accounts."""

    async def find_member_id_by_email(self, email: str) -> UUID | None: ...
    async def find_member_id_by_slug(self, slug: str) -> UUID | None: ...
    async def find_member_slug_by_id(self, member_id: UUID) -> str | None: ...


class DevMemberDirectory(Protocol):
    """What the development login needs on top of :class:`MemberDirectory`.

    Kept separate, and implemented by the same adapter, because it includes a *write* to
    ``members.email``. That is community's column; identity has no business touching it
    outside the impersonation convenience described in ``dev_login_service``, and a distinct
    port is how that stays visible.
    """

    async def get_member_by_slug(self, slug: str) -> MemberSummary | None: ...
    async def set_member_email(self, member_id: UUID, email: str) -> None: ...
    async def search_members(self, query: str | None, *, limit: int) -> list[MemberSummary]: ...
