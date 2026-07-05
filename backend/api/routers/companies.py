"""Company CRUD routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.api.deps import CompanyServiceDep
from backend.api.schemas.companies_public import CompaniesPublic, CompanyPublic
from backend.companies.services.commands import CompanyCreate, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=CompaniesPublic, status_code=200)
def list_companies(
    service: CompanyServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    industry: Annotated[str | None, Query()] = None,
    is_cdtm_startup: Annotated[bool | None, Query()] = None,
    hq_city: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=128)] = None,
) -> CompaniesPublic:
    page = service.list_companies(
        skip=skip,
        limit=limit,
        industry=industry,
        is_cdtm_startup=is_cdtm_startup,
        hq_city=hq_city,
        q=q,
    )
    return CompaniesPublic(
        items=[CompanyPublic.model_validate(c) for c in page.items],
        total=page.total,
    )


@router.get("/slug/{slug}", response_model=CompanyPublic, status_code=200)
def get_company_by_slug(
    service: CompanyServiceDep,
    slug: str,
) -> CompanyPublic:
    row = service.get_company_by_slug(slug)
    return CompanyPublic.model_validate(row)


@router.get("/{company_id}", response_model=CompanyPublic, status_code=200)
def get_company(
    service: CompanyServiceDep,
    company_id: UUID,
) -> CompanyPublic:
    row = service.get_company(company_id)
    return CompanyPublic.model_validate(row)


@router.post("/", response_model=CompanyPublic, status_code=201)
def create_company(
    service: CompanyServiceDep,
    body: CompanyCreate,
) -> CompanyPublic:
    row = service.create_company(body)
    return CompanyPublic.model_validate(row)


@router.patch("/{company_id}", response_model=CompanyPublic, status_code=200)
def update_company(
    service: CompanyServiceDep,
    company_id: UUID,
    body: CompanyUpdate,
) -> CompanyPublic:
    row = service.update_company(company_id, body)
    return CompanyPublic.model_validate(row)


@router.delete("/{company_id}", status_code=204)
def delete_company(
    service: CompanyServiceDep,
    company_id: UUID,
) -> Response:
    service.delete_company(company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
