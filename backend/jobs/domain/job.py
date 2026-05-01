"""Job posting aggregate — content, comp, location, process, audit."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    WORKING_STUDENT = "working_student"
    FREELANCE = "freelance"


class WorkArrangement(StrEnum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class SalaryPeriod(StrEnum):
    YEARLY = "yearly"
    MONTHLY = "monthly"
    HOURLY = "hourly"


class ExperienceLevel(StrEnum):
    INTERN = "intern"
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


class JobStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    FILLED = "filled"


class CompensationDisclosure(StrEnum):
    PUBLIC = "public"
    CONFIDENTIAL = "confidential"
    UNDISCLOSED = "undisclosed"


class Job(BaseModel):
    """A job opening posted by a company."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    company_id: UUID
    slug: str | None = Field(default=None, max_length=128)

    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=1024)
    description: str = Field(min_length=1)

    employment_type: EmploymentType
    work_arrangement: WorkArrangement

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

    experience_level: ExperienceLevel
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

    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
