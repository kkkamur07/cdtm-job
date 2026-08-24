"""AuthService against fakes: domain allow-list, account upsert, e-mail binding."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.core.exceptions import ForbiddenError, UnauthorizedError
from backend.identity.application.auth_service import AuthService
from backend.identity.domain import Account, TokenClaims


class _Verifier:
    def __init__(self, claims: TokenClaims) -> None:
        self._claims = claims

    async def verify_async(self, token: str) -> TokenClaims:
        # The whole port: one awaitable method, because the real verifier may have to push a
        # cold JWKS fetch onto a worker thread instead of blocking the event loop. Nothing to
        # await here; the fake is the whole check.
        return self._claims


class _Accounts:
    def __init__(self) -> None:
        self.rows: dict[UUID, Account] = {}

    async def get_by_auth_user_id(self, auth_user_id):
        return next((a for a in self.rows.values() if a.auth_user_id == auth_user_id), None)

    async def get_by_id(self, account_id):
        return self.rows.get(account_id)

    async def upsert_from_claims(self, claims, *, is_admin):
        existing = await self.get_by_auth_user_id(claims.sub)
        if existing:
            return existing
        now = datetime.now(UTC)
        acc = Account(
            id=uuid4(),
            auth_user_id=claims.sub,
            email=claims.email,
            is_admin=bool(is_admin),
            created_at=now,
            updated_at=now,
        )
        self.rows[acc.id] = acc
        return acc

    async def bind_member(self, account_id, member_id):
        acc = self.rows[account_id].model_copy(update={"member_id": member_id})
        self.rows[account_id] = acc
        return acc

    async def set_admin(self, account_id, is_admin):
        acc = self.rows[account_id].model_copy(update={"is_admin": is_admin})
        self.rows[account_id] = acc
        return acc


class _Members:
    def __init__(self, by_email: dict[str, UUID]) -> None:
        self._by_email = by_email

    async def find_member_id_by_email(self, email):
        return self._by_email.get(email)

    async def find_member_id_by_slug(self, slug):
        return None


def _service(
    claims: TokenClaims, *, members: dict[str, UUID] | None = None, admins: list[str] | None = None
):
    return AuthService(
        verifier=_Verifier(claims),
        accounts=_Accounts(),
        members=_Members(members or {}),
        allowed_email_domains=["cdtm.com"],
        admin_emails=admins or [],
    )


async def test_rejects_foreign_domains() -> None:
    svc = _service(TokenClaims(sub=uuid4(), email="someone@gmail.com", email_verified=True))
    with pytest.raises(ForbiddenError):
        await svc.authenticate("t")


async def test_binds_account_to_member_by_email_and_bootstraps_admin() -> None:
    member_id = uuid4()
    svc = _service(
        TokenClaims(sub=uuid4(), email="Anna.Test@cdtm.com", email_verified=True),
        members={"anna.test@cdtm.com": member_id},
        admins=["anna.test@cdtm.com"],
    )
    principal = await svc.authenticate("t")
    assert principal.member_id == member_id
    assert principal.is_admin is True
    assert principal.email == "anna.test@cdtm.com"


async def test_unmatched_email_leaves_account_unbound() -> None:
    svc = _service(TokenClaims(sub=uuid4(), email="new.person@cdtm.com", email_verified=True))
    principal = await svc.authenticate("t")
    assert principal.member_id is None
    assert principal.is_admin is False


async def test_unverified_email_is_rejected_even_on_an_allowed_domain() -> None:
    """An unverified address must never reach the allow-list check or the roster binding:
    it is not a fact about the caller yet, no matter whose domain it looks like."""
    member_id = uuid4()
    svc = _service(
        TokenClaims(sub=uuid4(), email="anna.test@cdtm.com", email_verified=False),
        members={"anna.test@cdtm.com": member_id},
    )
    with pytest.raises(UnauthorizedError):
        await svc.authenticate("t")


async def test_unverified_email_default_is_rejected() -> None:
    """``email_verified`` defaults to False on the claims model; a claim nobody made must
    not be treated as though Supabase made it."""
    svc = _service(TokenClaims(sub=uuid4(), email="anna.test@cdtm.com"))
    with pytest.raises(UnauthorizedError):
        await svc.authenticate("t")
