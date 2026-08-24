from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import (
    AdminPrincipalDep,
    AuthServiceDep,
    PrincipalDep,
)
from backend.identity.api.schemas import (
    AccountPublic,
    AccountsPublic,
    BindMemberRequest,
    MePublic,
    SetAdminRequest,
)
from backend.identity.domain import Principal

router = APIRouter(prefix="/auth", tags=["auth"])


def me_public(principal: Principal, member_slug: str | None) -> MePublic:
    """Build the ``/auth/me`` payload. Shared with the development login, which answers with
    the same shape so the frontend has one place to read the session from."""
    return MePublic(
        account=AccountPublic.model_validate(principal.account),
        member_id=principal.member_id,
        member_slug=member_slug,
        is_admin=principal.is_admin,
    )


@router.get("/me", response_model=MePublic)
async def me(principal: PrincipalDep, service: AuthServiceDep) -> MePublic:
    return me_public(principal, await service.find_member_slug(principal))


@router.get("/accounts", response_model=AccountsPublic)
async def list_accounts(
    actor: AdminPrincipalDep,
    service: AuthServiceDep,
    page: PageParamsDep,
    unbound: Annotated[bool, Query(description="only accounts no Member is bound to yet")] = False,
) -> AccountsPublic:
    """The admin's worklist: who has signed in, and which of them still need a Member.

    An Account with no Member is a Workspace mailbox the loader matched to no roster row.
    This is what a bind page reads before it calls ``POST /auth/accounts/{id}/bind``.
    """
    result = await service.list_accounts(
        actor=actor, skip=page.skip, limit=page.limit, unbound_only=unbound
    )
    return AccountsPublic(
        items=[AccountPublic.model_validate(a) for a in result.items], total=result.total
    )


@router.post("/accounts/{account_id}/bind", response_model=AccountPublic)
async def bind_member(
    account_id: UUID, body: BindMemberRequest, actor: AdminPrincipalDep, service: AuthServiceDep
) -> AccountPublic:
    account = await service.bind_account_to_member(
        actor=actor, account_id=account_id, member_slug=body.member_slug
    )
    return AccountPublic.model_validate(account)


@router.post("/accounts/{account_id}/admin", response_model=AccountPublic)
async def set_admin(
    account_id: UUID, body: SetAdminRequest, actor: AdminPrincipalDep, service: AuthServiceDep
) -> AccountPublic:
    account = await service.set_admin(actor=actor, account_id=account_id, is_admin=body.is_admin)
    return AccountPublic.model_validate(account)
