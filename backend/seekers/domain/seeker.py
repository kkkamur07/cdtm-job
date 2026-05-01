"""Seeker profile aggregate — identity, pitch, preferences, skills."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.jobs.domain.job import WorkArrangement


class Seeker(BaseModel):
    """A candidate profile on the job board."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    full_name: str = Field(min_length=1, max_length=255)

    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    linkedin_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    github_url: HttpUrl | None = None

    headline: str | None = Field(default=None, max_length=255)
    bio: str | None = None
    resume_url: HttpUrl | None = None

    open_to_remote: bool | None = None
    preferred_work_arrangement: WorkArrangement | None = None
    preferred_locations: list[str] = Field(default_factory=list)
    desired_role_titles: list[str] = Field(default_factory=list)

    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    education_summary: str | None = None
    available_from: date | None = None

    created_at: datetime
    updated_at: datetime
