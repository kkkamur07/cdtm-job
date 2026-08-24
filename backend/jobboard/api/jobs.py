from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from backend.core.api.pagination import PageParamsDep
from backend.identity.api.deps import ActorDep, OptionalActorDep, PrincipalDep
from backend.jobboard.api.deps import JobServiceDep
from backend.jobboard.api.schemas import JobPublic, JobsPublic
from backend.jobboard.application.commands import JobCreate, JobUpdate
from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import EmploymentType, JobStatus, WorkArrangement

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=JobsPublic)
async def list_jobs(
    service: JobServiceDep,
    page: PageParamsDep,
    actor: OptionalActorDep,
    company_id: Annotated[UUID | None, Query()] = None,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    employment_type: Annotated[EmploymentType | None, Query()] = None,
    work_arrangement: Annotated[WorkArrangement | None, Query()] = None,
    posted_by_member_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=128)] = None,
) -> JobsPublic:
    """Reading the board is public, but only the published part of it is.

    ``status`` is honoured for an admin and for a member asking for their own postings
    (``posted_by_member_id`` is their own id); for everybody else the board is pinned to
    published, whatever they asked for.
    """
    result = await service.list_jobs(
        skip=page.skip,
        limit=page.limit,
        filters=JobFilters(
            company_id=company_id,
            status=job_status,
            employment_type=employment_type,
            work_arrangement=work_arrangement,
            posted_by_member_id=posted_by_member_id,
            q=q,
        ),
        actor=actor,
    )
    return JobsPublic(items=[JobPublic.model_validate(j) for j in result.items], total=result.total)


@router.get("/slug/{slug}", response_model=JobPublic)
async def get_job_by_slug(service: JobServiceDep, slug: str, actor: OptionalActorDep) -> JobPublic:
    return JobPublic.model_validate(await service.get_job_by_slug(slug, actor))


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(service: JobServiceDep, job_id: UUID, actor: OptionalActorDep) -> JobPublic:
    return JobPublic.model_validate(await service.get_job(job_id, actor))


@router.post("/", response_model=JobPublic, status_code=201)
async def create_job(service: JobServiceDep, body: JobCreate, principal: PrincipalDep) -> JobPublic:
    """The job is attributed to the caller. The body cannot carry a poster id at all."""
    return JobPublic.model_validate(
        await service.create_job(body, posted_by_member_id=principal.member_id)
    )


@router.patch("/{job_id}", response_model=JobPublic)
async def update_job(
    service: JobServiceDep, job_id: UUID, body: JobUpdate, actor: ActorDep
) -> JobPublic:
    return JobPublic.model_validate(await service.update_job(actor, job_id, body))


@router.delete("/{job_id}", status_code=204)
async def delete_job(service: JobServiceDep, job_id: UUID, actor: ActorDep) -> Response:
    await service.delete_job(actor, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
