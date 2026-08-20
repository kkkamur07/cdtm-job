"""Persistence ports for jobs."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.core.page import PageResult
from backend.jobs.domain.job import Job, JobStatus
from backend.jobs.services.commands import JobCreate, JobUpdate


class JobRepository(Protocol):
    def list(
        self,
        *,
        skip: int,
        limit: int,
        company_id: UUID | None,
        status: JobStatus | None,
    ) -> PageResult[Job]: ...

    def get(self, job_id: UUID) -> Job | None: ...

    def get_by_slug(self, slug: str) -> Job | None: ...

    def create(self, payload: JobCreate) -> Job: ...

    def update(self, job_id: UUID, payload: JobUpdate) -> Job | None: ...

    def delete(self, job_id: UUID) -> bool: ...
