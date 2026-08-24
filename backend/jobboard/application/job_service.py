"""Application service: use-case orchestration for job."""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult
from backend.jobboard.application.commands import (
    JobCreate,
    JobUpdate,
)
from backend.jobboard.application.ports import (
    JobFilters,
    JobRepository,
)
from backend.jobboard.application.visibility import (
    can_manage_job,
    can_see_job,
    job_filters_for,
    job_for_viewer,
)
from backend.jobboard.domain import Job


class JobService:
    def __init__(self, repo: JobRepository) -> None:
        self._repo = repo

    async def list_jobs(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        filters: JobFilters | None = None,
        actor: Actor | None = None,
    ) -> PageResult[Job]:
        result = await self._repo.list(
            skip=skip, limit=limit, filters=job_filters_for(filters or JobFilters(), actor)
        )
        return PageResult(
            items=[job_for_viewer(j, actor) for j in result.items], total=result.total
        )

    async def get_job(self, job_id: UUID, actor: Actor | None = None) -> Job:
        row = await self._repo.get(job_id)
        if row is None or not can_see_job(row, actor):
            # A draft nobody has decided to advertise is not a job this caller may know
            # exists, so it is absent rather than forbidden.
            raise NotFoundError(f"Job {job_id} not found")
        return job_for_viewer(row, actor)

    async def get_job_by_slug(self, slug: str, actor: Actor | None = None) -> Job:
        row = await self._repo.get_by_slug(slug)
        if row is None or not can_see_job(row, actor):
            raise NotFoundError(f"Job slug {slug!r} not found")
        return job_for_viewer(row, actor)

    async def create_job(self, payload: JobCreate, *, posted_by_member_id: UUID | None) -> Job:
        """The poster is whoever is signed in. Callers cannot name someone else."""
        return await self._repo.create(payload, posted_by_member_id=posted_by_member_id)

    async def update_job(self, actor: Actor, job_id: UUID, payload: JobUpdate) -> Job:
        await self._owned(actor, job_id, "edit")
        row = await self._repo.update(job_id, payload)
        if row is None:
            raise NotFoundError(f"Job {job_id} not found")
        return row

    async def delete_job(self, actor: Actor, job_id: UUID) -> None:
        await self._owned(actor, job_id, "delete")
        if not await self._repo.delete(job_id):
            raise NotFoundError(f"Job {job_id} not found")

    async def _owned(self, actor: Actor, job_id: UUID, what: str) -> Job:
        """Ownership, not visibility, gates a write.

        Editing or deleting a row is a different question from being allowed to discover it:
        a caller who already holds this exact id (it is an unguessable UUID, never something
        browsing the board hands out) does not learn anything about the job's draft status
        from a 403, only that they do not own it. Gating the write on ``can_see_job`` used to
        answer "may you know this id exists" instead of "may you change this row", which
        turned a non-owner's edit attempt on a draft into a 404 instead of the 403 that every
        other non-owner write on the board gets.
        """
        row = await self._repo.get(job_id)
        if row is None:
            raise NotFoundError(f"Job {job_id} not found")
        if not can_manage_job(row, actor):
            raise ForbiddenError(f"only the poster or an admin can {what} this job")
        return row
