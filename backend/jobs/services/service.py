"""Job application service — CRUD orchestration."""

from __future__ import annotations

from uuid import UUID

from backend.core.errors import NotFoundError
from backend.core.page import PageResult
from backend.jobs.domain.job import Job, JobStatus
from backend.jobs.services.commands import JobCreate, JobUpdate
from backend.jobs.services.ports import JobRepository


class JobService:
    def __init__(self, repo: JobRepository) -> None:
        self._repo = repo

    def list_jobs(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        company_id: UUID | None = None,
        status: JobStatus | None = None,
    ) -> PageResult[Job]:
        skip = max(skip, 0)
        limit = min(max(limit, 1), 100)
        return self._repo.list(
            skip=skip,
            limit=limit,
            company_id=company_id,
            status=status,
        )

    def get_job(self, job_id: UUID) -> Job:
        row = self._repo.get(job_id)
        if row is None:
            raise NotFoundError(f"Job {job_id} not found")
        return row

    def get_job_by_slug(self, slug: str) -> Job:
        row = self._repo.get_by_slug(slug)
        if row is None:
            raise NotFoundError(f"Job slug {slug!r} not found")
        return row

    def create_job(self, payload: JobCreate) -> Job:
        return self._repo.create(payload)

    def update_job(self, job_id: UUID, payload: JobUpdate) -> Job:
        row = self._repo.update(job_id, payload)
        if row is None:
            raise NotFoundError(f"Job {job_id} not found")
        return row

    def delete_job(self, job_id: UUID) -> None:
        if not self._repo.delete(job_id):
            raise NotFoundError(f"Job {job_id} not found")
