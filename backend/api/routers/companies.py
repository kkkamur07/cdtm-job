"""Company CRUD routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.api.deps import CompanyServiceDep
from backend.api.route_errors import rethrow_as_http
from backend.api.schemas.companies_public import CompaniesPublic, CompanyPublic
from backend.companies.services.commands import CompanyCreate, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=CompaniesPublic, status_code=200)
def list_companies(
    service: CompanyServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CompaniesPublic:
    try:
        page = service.list_companies(skip=skip, limit=limit)
        return CompaniesPublic(
            items=[CompanyPublic.model_validate(c.model_dump()) for c in page.items],
            total=page.total,
        )
    except Exception as exc:
        rethrow_as_http(exc)


@router.get("/{company_id}", response_model=CompanyPublic, status_code=200)
def get_company(
    service: CompanyServiceDep,
    company_id: UUID,
) -> CompanyPublic:
    try:
        row = service.get_company(company_id)
        return CompanyPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.get("/slug/{slug}", response_model=CompanyPublic, status_code=200)
def get_company_by_slug(
    service: CompanyServiceDep,
    slug: str,
) -> CompanyPublic:
    try:
        row = service.get_company_by_slug(slug)
        return CompanyPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.post("/", response_model=CompanyPublic, status_code=201)
def create_company(
    service: CompanyServiceDep,
    body: CompanyCreate,
) -> CompanyPublic:
    try:
        row = service.create_company(body)
        return CompanyPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.patch("/{company_id}", response_model=CompanyPublic, status_code=200)
def update_company(
    service: CompanyServiceDep,
    company_id: UUID,
    body: CompanyUpdate,
) -> CompanyPublic:
    try:
        row = service.update_company(company_id, body)
        return CompanyPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.delete("/{company_id}", status_code=204)
def delete_company(
    service: CompanyServiceDep,
    company_id: UUID,
) -> Response:
    try:
        service.delete_company(company_id)
    except Exception as exc:
        rethrow_as_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
