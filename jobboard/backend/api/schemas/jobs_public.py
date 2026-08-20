"""Public API models for jobs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.jobs.domain.job import Job


class JobPublic(Job):
    """Response body for a single job."""

    model_config = ConfigDict(title="JobPublic")


class JobsPublic(BaseModel):
    """Paginated job list."""

    model_config = ConfigDict(extra="forbid")

    items: list[JobPublic]
    total: int
