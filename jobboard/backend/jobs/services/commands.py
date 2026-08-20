"""Write models for jobs (application layer)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.jobs.domain.job import (
    CompensationDisclosure,
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    SalaryPeriod,
    WorkArrangement,
)


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    employment_type: EmploymentType
    work_arrangement: WorkArrangement
    experience_level: ExperienceLevel

    slug: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=1024)
    location_display: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    remote_eligibility_note: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: SalaryPeriod | None = None
    compensation_disclosure: CompensationDisclosure = CompensationDisclosure.UNDISCLOSED
    education_level: str | None = Field(default=None, max_length=128)
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    application_url: HttpUrl | None = None
    application_email: str | None = Field(default=None, max_length=255)
    valid_through: date | None = None
    status: JobStatus = JobStatus.DRAFT
    visa_sponsorship: bool | None = None
    relocation_assistance: bool | None = None


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    employment_type: EmploymentType | None = None
    work_arrangement: WorkArrangement | None = None
    experience_level: ExperienceLevel | None = None
    slug: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=1024)
    location_display: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    remote_eligibility_note: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: SalaryPeriod | None = None
    compensation_disclosure: CompensationDisclosure | None = None
    education_level: str | None = Field(default=None, max_length=128)
    must_have_skills: list[str] | None = None
    nice_to_have_skills: list[str] | None = None
    languages: list[str] | None = None
    application_url: HttpUrl | None = None
    application_email: str | None = Field(default=None, max_length=255)
    valid_through: date | None = None
    status: JobStatus | None = None
    visa_sponsorship: bool | None = None
    relocation_assistance: bool | None = None
    published_at: datetime | None = None
