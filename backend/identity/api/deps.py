"""FastAPI dependencies: bearer token -> Principal -> Actor. Other contexts import from here.

A board never sees a Principal. It asks for an ``Actor``, which is the member id and the
admin flag and nothing else an Account happens to know, and the translation happens in the
three functions at the bottom of this module. That is the only seam every other context is
allowed to have with identity.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.actor import Actor
from backend.core.exceptions import AppError, ForbiddenError, UnauthorizedError
from backend.core.settings import get_auth_settings
from backend.identity.application.auth_service import AuthService
from backend.identity.application.dev_login_service import DevLoginService
from backend.identity.application.ports import TokenVerifier
from backend.identity.domain import Principal
from backend.identity.infrastructure.account_repository import SqlAccountRepository
from backend.identity.infrastructure.dev_token_issuer import DevTokenIssuer
from backend.identity.infrastructure.jwt_verifier import SupabaseJwtVerifier
from backend.identity.infrastructure.member_directory import SqlMemberDirectory
from infrastructure.db import get_db

DbDep = Annotated[AsyncSession, Depends(get_db)]


@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifier:
    s = get_auth_settings()
    return SupabaseJwtVerifier(
        jwt_secret=s.jwt_secret,
        jwks_url=s.jwks_url,
        audience=s.jwt_audience,
        jwks_cache_seconds=s.jwks_cache_seconds,
    )


def get_auth_service(
    db: DbDep, verifier: Annotated[TokenVerifier, Depends(get_token_verifier)]
) -> AuthService:
    s = get_auth_settings()
    return AuthService(
        verifier=verifier,
        accounts=SqlAccountRepository(db),
        members=SqlMemberDirectory(db),
        allowed_email_domains=s.allowed_email_domains,
        admin_emails=s.admin_emails,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_dev_login_service(db: DbDep, auth: AuthServiceDep) -> DevLoginService:
    s = get_auth_settings()
    if not s.jwt_secret:
        # create_app refuses to boot in this state; reaching here means the flag was flipped
        # after startup, which is worth an explicit error rather than a signing traceback.
        raise AppError("dev login requires SUPABASE_JWT_SECRET to be set")
    return DevLoginService(
        auth=auth,
        issuer=DevTokenIssuer(jwt_secret=s.jwt_secret, audience=s.jwt_audience),
        members=SqlMemberDirectory(db),
        # The domain a roster row with no Workspace address is claimed on. First in the
        # allow-list, so the address the service derives passes the same check as any other.
        default_email_domain=(s.allowed_email_domains or ["cdtm.com"])[0],
    )


DevLoginServiceDep = Annotated[DevLoginService, Depends(get_dev_login_service)]


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("expected 'Authorization: Bearer <token>'")
    return token


async def get_optional_principal(
    service: AuthServiceDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal | None:
    token = _bearer(authorization)
    if token is None:
        return None
    return await service.authenticate(token)


async def get_current_principal(
    principal: Annotated[Principal | None, Depends(get_optional_principal)],
) -> Principal:
    if principal is None:
        raise UnauthorizedError("authentication required")
    return principal


async def get_current_member_principal(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    """A signed-in account that is bound to a Member (needed to write anything member-owned)."""
    if principal.member_id is None:
        raise ForbiddenError(
            "your account is not linked to a member entry yet",
            details={"hint": "ask an admin to link your account"},
        )
    return principal


async def get_admin_principal(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    if not principal.is_admin:
        raise ForbiddenError("admin only")
    return principal


OptionalPrincipalDep = Annotated[Principal | None, Depends(get_optional_principal)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
MemberPrincipalDep = Annotated[Principal, Depends(get_current_member_principal)]
AdminPrincipalDep = Annotated[Principal, Depends(get_admin_principal)]


# ---- Principal -> Actor, the seam every board uses ------------------------------------


def get_optional_actor(principal: OptionalPrincipalDep) -> Actor | None:
    return Actor(principal.member_id, principal.is_admin) if principal else None


def get_actor(principal: PrincipalDep) -> Actor:
    return Actor(principal.member_id, principal.is_admin)


def get_member_actor(principal: MemberPrincipalDep) -> Actor:
    return Actor(principal.member_id, principal.is_admin)


OptionalActorDep = Annotated[Actor | None, Depends(get_optional_actor)]
ActorDep = Annotated[Actor, Depends(get_actor)]
MemberActorDep = Annotated[Actor, Depends(get_member_actor)]
