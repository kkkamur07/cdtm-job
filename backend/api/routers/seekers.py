"""Seeker CRUD routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.api.deps import SeekerServiceDep
from backend.api.route_errors import rethrow_as_http
from backend.api.schemas.seekers_public import SeekerPublic, SeekersPublic
from backend.seekers.services.commands import SeekerCreate, SeekerUpdate

router = APIRouter(prefix="/seekers", tags=["seekers"])


@router.get("/", response_model=SeekersPublic, status_code=200)
def list_seekers(
    service: SeekerServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SeekersPublic:
    try:
        page = service.list_seekers(skip=skip, limit=limit)
        return SeekersPublic(
            items=[SeekerPublic.model_validate(s.model_dump()) for s in page.items],
            total=page.total,
        )
    except Exception as exc:
        rethrow_as_http(exc)


@router.get("/{seeker_id}", response_model=SeekerPublic, status_code=200)
def get_seeker(
    service: SeekerServiceDep,
    seeker_id: UUID,
) -> SeekerPublic:
    try:
        row = service.get_seeker(seeker_id)
        return SeekerPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.post("/", response_model=SeekerPublic, status_code=201)
def create_seeker(
    service: SeekerServiceDep,
    body: SeekerCreate,
) -> SeekerPublic:
    try:
        row = service.create_seeker(body)
        return SeekerPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.patch("/{seeker_id}", response_model=SeekerPublic, status_code=200)
def update_seeker(
    service: SeekerServiceDep,
    seeker_id: UUID,
    body: SeekerUpdate,
) -> SeekerPublic:
    try:
        row = service.update_seeker(seeker_id, body)
        return SeekerPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.delete("/{seeker_id}", status_code=204)
def delete_seeker(
    service: SeekerServiceDep,
    seeker_id: UUID,
) -> Response:
    try:
        service.delete_seeker(seeker_id)
    except Exception as exc:
        rethrow_as_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
