"""Job CRUD routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.api.deps import JobServiceDep
from backend.api.route_errors import rethrow_as_http
from backend.api.schemas.jobs_public import JobPublic, JobsPublic
from backend.jobs.domain.job import JobStatus
from backend.jobs.services.commands import JobCreate, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=JobsPublic, status_code=200)
def list_jobs(
    service: JobServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    company_id: Annotated[UUID | None, Query()] = None,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
) -> JobsPublic:
    try:
        page = service.list_jobs(
            skip=skip,
            limit=limit,
            company_id=company_id,
            status=job_status,
        )
        return JobsPublic(
            items=[JobPublic.model_validate(j.model_dump()) for j in page.items],
            total=page.total,
        )
    except Exception as exc:
        rethrow_as_http(exc)


@router.get("/{job_id}", response_model=JobPublic, status_code=200)
def get_job(
    service: JobServiceDep,
    job_id: UUID,
) -> JobPublic:
    try:
        row = service.get_job(job_id)
        return JobPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.get("/slug/{slug}", response_model=JobPublic, status_code=200)
def get_job_by_slug(
    service: JobServiceDep,
    slug: str,
) -> JobPublic:
    try:
        row = service.get_job_by_slug(slug)
        return JobPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.post("/", response_model=JobPublic, status_code=201)
def create_job(
    service: JobServiceDep,
    body: JobCreate,
) -> JobPublic:
    try:
        row = service.create_job(body)
        return JobPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.patch("/{job_id}", response_model=JobPublic, status_code=200)
def update_job(
    service: JobServiceDep,
    job_id: UUID,
    body: JobUpdate,
) -> JobPublic:
    try:
        row = service.update_job(job_id, body)
        return JobPublic.model_validate(row.model_dump())
    except Exception as exc:
        rethrow_as_http(exc)


@router.delete("/{job_id}", status_code=204)
def delete_job(
    service: JobServiceDep,
    job_id: UUID,
) -> Response:
    try:
        service.delete_job(job_id)
    except Exception as exc:
        rethrow_as_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
