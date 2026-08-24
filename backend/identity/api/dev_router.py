"""Development-only sign-in routes.

``create_app`` includes this router only when ``AUTH_DEV_LOGIN_ENABLED`` is set, so with the
flag off the paths are a 404 and, more importantly, absent from the OpenAPI document the
frontend client is generated from. The same boot check refuses to start at all if the flag is
on in production.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from backend.identity.api.deps import DevLoginServiceDep
from backend.identity.api.router import me_public
from backend.identity.api.schemas import DevLoginRequest, DevLoginResponse, DevMemberOption

router = APIRouter(prefix="/auth/dev", tags=["auth-dev"])

#: A picker, not a directory listing. Twenty rows is enough to choose from after typing.
MEMBER_PICKER_LIMIT = 20


@router.post("/login", response_model=DevLoginResponse)
async def dev_login(body: DevLoginRequest, service: DevLoginServiceDep) -> DevLoginResponse:
    """Mint a local access token and sign in with it.

    ``member_slug`` names the Member to become; the address is read from that roster row, or
    written onto it when it has none, and still has to pass the domain allow-list. A row
    already claimed by a different address is a 409. ``email`` is accepted for one transition
    while the frontend catches up.
    """
    result = await service.login(member_slug=body.member_slug, email=body.email)
    return DevLoginResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        me=me_public(result.principal, result.member_slug),
    )


@router.get("/members", response_model=list[DevMemberOption])
async def dev_members(
    service: DevLoginServiceDep,
    q: Annotated[str | None, Query(max_length=128)] = None,
) -> list[DevMemberOption]:
    """Members to impersonate, matched on name or slug.

    Unauthenticated on purpose: it feeds the picker on the local sign-in screen, which is
    what the caller uses *before* they have a token. It returns a capped list rather than the
    usual ``{items, total}`` page because it is a type-ahead, not a collection.

    The reply carries the slug and not the e-mail. The slug is what ``POST /auth/dev/login``
    wants, and an unauthenticated route has no business handing out a page of real Workspace
    addresses however development-only it is.
    """
    members = await service.search_members(q, limit=MEMBER_PICKER_LIMIT)
    return [
        DevMemberOption(id=m.id, slug=m.slug, name=m.name, class_label=m.class_label)
        for m in members
    ]
