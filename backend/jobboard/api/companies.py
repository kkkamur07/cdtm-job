from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import ActorDep, PrincipalDep
from backend.jobboard.api.deps import CompanyServiceDep
from backend.jobboard.api.schemas import CompaniesPublic, CompanyPublic
from backend.jobboard.application.commands import CompanyCreate, CompanyUpdate
from backend.jobboard.application.ports import CompanyFilters

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=CompaniesPublic)
async def list_companies(
    service: CompanyServiceDep,
    page: PageParamsDep,
    industry: Annotated[str | None, Query()] = None,
    is_cdtm_startup: Annotated[bool | None, Query()] = None,
    hq_city: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=128)] = None,
) -> CompaniesPublic:
    result = await service.list_companies(
        skip=page.skip,
        limit=page.limit,
        filters=CompanyFilters(
            industry=industry, is_cdtm_startup=is_cdtm_startup, hq_city=hq_city, q=q
        ),
    )
    return CompaniesPublic(
        items=[CompanyPublic.model_validate(c) for c in result.items], total=result.total
    )


@router.get("/slug/{slug}", response_model=CompanyPublic)
async def get_company_by_slug(service: CompanyServiceDep, slug: str) -> CompanyPublic:
    return CompanyPublic.model_validate(await service.get_company_by_slug(slug))


@router.get("/{company_id}", response_model=CompanyPublic)
async def get_company(service: CompanyServiceDep, company_id: UUID) -> CompanyPublic:
    return CompanyPublic.model_validate(await service.get_company(company_id))


@router.post("/", response_model=CompanyPublic, status_code=201)
async def create_company(
    service: CompanyServiceDep, body: CompanyCreate, principal: PrincipalDep
) -> CompanyPublic:
    """The record is attributed to the caller. The body cannot carry a creator id at all."""
    return CompanyPublic.model_validate(
        await service.create_company(body, created_by_member_id=principal.member_id)
    )


@router.patch("/{company_id}", response_model=CompanyPublic)
async def update_company(
    service: CompanyServiceDep, company_id: UUID, body: CompanyUpdate, actor: ActorDep
) -> CompanyPublic:
    return CompanyPublic.model_validate(await service.update_company(actor, company_id, body))


@router.delete("/{company_id}", status_code=204)
async def delete_company(service: CompanyServiceDep, company_id: UUID, actor: ActorDep) -> Response:
    """Admin only: a Company cascades to every Job posted under it."""
    await service.delete_company(actor, company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
