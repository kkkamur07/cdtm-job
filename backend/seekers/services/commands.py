"""Write models for seekers (application layer)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.jobs.domain.job import WorkArrangement


class SeekerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class SeekerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
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
    preferred_locations: list[str] | None = None
    desired_role_titles: list[str] | None = None
    skills: list[str] | None = None
    languages: list[str] | None = None
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    education_summary: str | None = None
    available_from: date | None = None
