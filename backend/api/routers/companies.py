"""Company HTTP routes.

FastAPI basics (quick map):
- **APIRouter**: a bag of routes (path + method + handler) you mount on the app with a
  shared ``prefix`` and OpenAPI ``tags``.
- **Depends(...)**: dependency injection — FastAPI calls your function (e.g. ``get_supabase``)
  per request and passes the return value into the route handler parameter. Use it for DB
  clients, settings, auth, and **constructing application services** (thin controllers).
- **@router.patch**: registers **HTTP PATCH** — partial update semantics (conventionally:
  only send fields you want to change). We return **204 No Content** when there is no JSON body.
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from api.deps import get_supabase
from companies.application.commands import CreateCompanyCommand, UpdateCompanyCommand
from companies.application.service import CompanyService
from companies.infrastructure.repository import SupabaseCompanyRepository

router = APIRouter(prefix="/companies", tags=["companies"])


def get_company_service(client: Client = Depends(get_supabase)) -> CompanyService:
    """Inject a ``CompanyService`` wired to Supabase for this request."""
    return CompanyService(SupabaseCompanyRepository(client))


@router.get("/")
async def list_companies(
    service: CompanyService = Depends(get_company_service),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, list]:
    rows = await asyncio.to_thread(lambda: service.list_companies(limit=limit))

    return {"items": rows}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CreateCompanyCommand,
    service: CompanyService = Depends(get_company_service),
) -> dict[str, UUID]:
    try:
        company_id = await asyncio.to_thread(service.create_company, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {"id": company_id}


@router.get("/slug/{slug}")
async def get_company_by_slug(
    slug: str,
    service: CompanyService = Depends(get_company_service),
) -> dict:
    row = await asyncio.to_thread(service.get_company_by_slug, slug)

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return row


@router.get("/{company_id}")
async def get_company(
    company_id: UUID,
    service: CompanyService = Depends(get_company_service),
) -> dict:
    row = await asyncio.to_thread(service.get_company, company_id)

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return row


@router.patch("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_company(
    company_id: UUID,
    body: UpdateCompanyCommand,
    service: CompanyService = Depends(get_company_service),
) -> None:
    """HTTP PATCH: apply a **partial** update from ``UpdateCompanyCommand`` (unset = unchanged)."""
    try:
        await asyncio.to_thread(lambda: service.update_company(company_id, body))
    except ValueError as e:
        msg = str(e)

        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    service: CompanyService = Depends(get_company_service),
) -> None:
    deleted = await asyncio.to_thread(service.delete_company, company_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
