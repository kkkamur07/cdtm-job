from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import StringConstraints

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import OptionalActorDep, PrincipalDep
from backend.members.api.deps import MemberServiceDep
from backend.members.api.schemas import (
    ClassPublic,
    CompanyContactPublic,
    CompanyContactsPublic,
    DirectoryFacets,
    MemberProfilePublic,
    MemberPublic,
    MembersPublic,
)
from backend.members.application.member_service import FACETS_TTL_SECONDS
from backend.members.application.ports import MemberFilters

router = APIRouter(prefix="/members", tags=["members"])

_INTENTS = ("cofounding", "mentoring", "hiring", "open_to_roles", "speaking", "investing")

#: Longest company name a caller may send, per name. The same ceiling ``?company=`` has,
#: because both ends up in the same ILIKE against the directory.
MAX_COMPANY_NAME = 128


@router.get("/", response_model=MembersPublic)
async def search_members(
    service: MemberServiceDep,
    page: PageParamsDep,
    actor: OptionalActorDep,
    _: PrincipalDep,
    q: Annotated[str | None, Query(max_length=128)] = None,
    class_id: Annotated[int | None, Query()] = None,
    class_label: Annotated[str | None, Query(max_length=64)] = None,
    major: Annotated[str | None, Query(max_length=128)] = None,
    role: Annotated[str | None, Query(pattern="^(student|ca|faculty)$")] = None,
    location: Annotated[str | None, Query(max_length=128)] = None,
    company: Annotated[str | None, Query(max_length=128)] = None,
    intent: Annotated[
        list[str] | None, Query(description="repeatable; any of " + ", ".join(_INTENTS))
    ] = None,
    skill: Annotated[list[str] | None, Query()] = None,
    is_ca: Annotated[bool | None, Query()] = None,
    has_entry: Annotated[bool | None, Query()] = None,
    claimed_only: Annotated[bool, Query()] = False,
    needs_review: Annotated[bool | None, Query(description="admin only")] = None,
) -> MembersPublic:
    filters = MemberFilters(
        q=q,
        class_id=class_id,
        class_label=class_label,
        major=major,
        role=role,
        location=location,
        company=company,
        intents=tuple(i for i in (intent or []) if i in _INTENTS),
        skills=tuple(skill or []),
        is_ca=is_ca,
        has_entry=has_entry,
        claimed_only=claimed_only,
        needs_review=needs_review,
    )
    result = await service.search(skip=page.skip, limit=page.limit, filters=filters, actor=actor)
    return MembersPublic(
        items=[MemberPublic.model_validate(m) for m in result.items], total=result.total
    )


@router.get("/lookup", response_model=MembersPublic)
async def lookup_members(
    service: MemberServiceDep,
    _: PrincipalDep,
    ids: Annotated[
        list[UUID],
        Query(
            max_length=50,
            description="Member ids to resolve to cards, for 'posted by' and similar.",
        ),
    ],
) -> MembersPublic:
    """Cards for up to 50 ids in one call, in the order asked for. Unknown ids are dropped."""
    members = await service.lookup(ids)
    return MembersPublic(
        items=[MemberPublic.model_validate(m) for m in members], total=len(members)
    )


@router.get("/at-company", response_model=CompanyContactsPublic)
async def members_at_companies(
    service: MemberServiceDep,
    _: PrincipalDep,
    company: Annotated[
        # ``max_length`` on the list is the number of names; the per-element constraint is
        # the length of one name. Without it a single 1 MB "name" became an ILIKE pattern
        # over the whole directory. 128 matches the ``?company=`` cap on the search route.
        list[Annotated[str, StringConstraints(max_length=MAX_COMPANY_NAME)]],
        Query(
            max_length=50,
            description="repeatable company name; one member is returned for each",
        ),
    ],
) -> CompanyContactsPublic:
    """One member per company name, for a page that lists many companies at once.

    The job board used to ask ``/members?company=<name>&limit=1`` once per row. Names that
    match nobody are left out; the answer keeps the order the names were asked in.
    """
    contacts = await service.contacts_at(company)
    return CompanyContactsPublic(
        items=[CompanyContactPublic.model_validate(c) for c in contacts], total=len(contacts)
    )


@router.get("/facets", response_model=DirectoryFacets)
async def facets(service: MemberServiceDep, response: Response, _: PrincipalDep) -> DirectoryFacets:
    """The directory's filter bar: every class, every major, and the roster size.

    ``private`` rather than ``public``: the route is behind a bearer token, so no shared
    cache may keep a copy, and the answer is the same for every caller anyway.
    """
    result = await service.facets()
    response.headers["Cache-Control"] = f"private, max-age={FACETS_TTL_SECONDS}"
    return DirectoryFacets(
        classes=[ClassPublic.model_validate(c) for c in result.classes],
        majors=list(result.majors),
        members_total=result.members_total,
    )


@router.get("/{slug}", response_model=MemberProfilePublic)
async def get_member(
    slug: str, service: MemberServiceDep, actor: OptionalActorDep, _: PrincipalDep
) -> MemberProfilePublic:
    return MemberProfilePublic.model_validate(await service.get_profile(slug, actor))
