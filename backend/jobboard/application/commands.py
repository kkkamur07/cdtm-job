"""Write models (commands) for the job board. PATCH semantics: only set fields apply."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.core.text import MAX_NOTE, MAX_RICH_TEXT
from backend.jobboard.domain.company import CompanySizeBand
from backend.jobboard.domain.job import (
    CompensationDisclosure,
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    SalaryPeriod,
    WorkArrangement,
)


class CompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)
    legal_name: str | None = Field(default=None, max_length=255)
    logo_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    careers_page_url: HttpUrl | None = None
    short_description: str | None = Field(default=None, max_length=512)
    full_description: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    industry: str | None = Field(default=None, max_length=128)
    company_size_band: CompanySizeBand | None = None
    is_cdtm_startup: bool = False
    hq_city: str | None = Field(default=None, max_length=128)
    hq_region: str | None = Field(default=None, max_length=128)
    hq_country: str | None = Field(default=None, max_length=128)
    linkedin_url: HttpUrl | None = None
    twitter_url: HttpUrl | None = None


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=128)
    legal_name: str | None = Field(default=None, max_length=255)
    logo_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    careers_page_url: HttpUrl | None = None
    short_description: str | None = Field(default=None, max_length=512)
    full_description: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    industry: str | None = Field(default=None, max_length=128)
    company_size_band: CompanySizeBand | None = None
    is_cdtm_startup: bool | None = None
    hq_city: str | None = Field(default=None, max_length=128)
    hq_region: str | None = Field(default=None, max_length=128)
    hq_country: str | None = Field(default=None, max_length=128)
    linkedin_url: HttpUrl | None = None
    twitter_url: HttpUrl | None = None


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=MAX_RICH_TEXT)
    employment_type: EmploymentType
    work_arrangement: WorkArrangement
    experience_level: ExperienceLevel

    slug: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=1024)
    location_display: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    remote_eligibility_note: str | None = Field(default=None, max_length=MAX_NOTE)
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: SalaryPeriod | None = None
    compensation_disclosure: CompensationDisclosure = CompensationDisclosure.UNDISCLOSED
    education_level: str | None = Field(default=None, max_length=128)
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    image_url: HttpUrl | None = None
    application_url: HttpUrl | None = None
    application_email: str | None = Field(default=None, max_length=255)
    valid_through: date | None = None
    status: JobStatus = JobStatus.DRAFT
    visa_sponsorship: bool | None = None
    relocation_assistance: bool | None = None


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=MAX_RICH_TEXT)
    employment_type: EmploymentType | None = None
    work_arrangement: WorkArrangement | None = None
    experience_level: ExperienceLevel | None = None
    slug: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=1024)
    location_display: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    remote_eligibility_note: str | None = Field(default=None, max_length=MAX_NOTE)
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_period: SalaryPeriod | None = None
    compensation_disclosure: CompensationDisclosure | None = None
    education_level: str | None = Field(default=None, max_length=128)
    must_have_skills: list[str] | None = None
    nice_to_have_skills: list[str] | None = None
    languages: list[str] | None = None
    image_url: HttpUrl | None = None
    application_url: HttpUrl | None = None
    application_email: str | None = Field(default=None, max_length=255)
    valid_through: date | None = None
    status: JobStatus | None = None
    visa_sponsorship: bool | None = None
    relocation_assistance: bool | None = None
    published_at: datetime | None = None


class SeekerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    linkedin_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    headline: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    resume_url: HttpUrl | None = None
    open_to_remote: bool | None = None
    preferred_work_arrangement: WorkArrangement | None = None
    preferred_locations: list[str] = Field(default_factory=list)
    desired_role_titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    education_summary: str | None = Field(default=None, max_length=MAX_NOTE)
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
    bio: str | None = Field(default=None, max_length=MAX_RICH_TEXT)
    resume_url: HttpUrl | None = None
    open_to_remote: bool | None = None
    preferred_work_arrangement: WorkArrangement | None = None
    preferred_locations: list[str] | None = None
    desired_role_titles: list[str] | None = None
    skills: list[str] | None = None
    languages: list[str] | None = None
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    education_summary: str | None = Field(default=None, max_length=MAX_NOTE)
    available_from: date | None = None
