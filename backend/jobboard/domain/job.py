"""Job posting aggregate: content, comp, location, process, audit."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, model_validator


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


def plain_salary(value: Decimal | None) -> Decimal | None:
    """Drop the storage column's fixed two decimals when they carry no information.

    ``Numeric(18, 2)`` always hands back ``60000.00``; a poster who typed a whole number
    should read the whole number back, not a figure that looks like it was entered to the
    cent. ``normalize()`` alone can flip an integer into exponential form (``1E+2``), so an
    exact integer is re-quantized to a plain value instead.

    A module function rather than a method, because the aggregate and the summary both
    serialize the same two columns and a row must never print a salary differently from the
    detail page that opens from it.
    """
    if value is None:
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return normalized.quantize(Decimal(1))
    return normalized


def _salary_range_is_ordered(salary_min: Decimal | None, salary_max: Decimal | None) -> None:
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise ValueError("salary_min must be <= salary_max")


class Job(BaseModel):
    """A job opening posted by a company, optionally on behalf of a community member."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    company_id: UUID
    posted_by_member_id: UUID | None = None
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

    image_url: HttpUrl | None = None
    application_url: HttpUrl | None = None
    application_email: str | None = Field(default=None, max_length=255)
    valid_through: date | None = None
    status: JobStatus = JobStatus.DRAFT
    visa_sponsorship: bool | None = None
    relocation_assistance: bool | None = None

    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    @model_validator(mode="after")
    def _salary_range(self) -> Job:
        _salary_range_is_ordered(self.salary_min, self.salary_max)
        return self

    @field_serializer("salary_min", "salary_max", when_used="json")
    def _plain_salary(self, value: Decimal | None) -> Decimal | None:
        return plain_salary(value)


class JobSummary(BaseModel):
    """A Job as the board lists it: everything a row draws, and none of the long text.

    The list query selects exactly these columns. ``description`` is capped at
    ``MAX_RICH_TEXT`` (twenty thousand characters) and a page is a hundred rows, so reading
    the aggregate to build a row pulled up to two megabytes of prose across the link and
    validated it into a full ``Job`` only to drop it again on the way out. The three keyword
    lists ride along with it: they are read on the detail page, next to the description.

    The fields are restated rather than inherited from ``Job``, because pydantic has no way
    to take a field back off a parent. ``tests/unit/test_list_summary_dtos.py`` pins this
    field set against the aggregate's, so a field added to ``Job`` fails there until somebody
    decides whether a list row should carry it.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    company_id: UUID
    posted_by_member_id: UUID | None = None
    slug: str | None = Field(default=None, max_length=128)

    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=1024)

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

    image_url: HttpUrl | None = None
    application_url: HttpUrl | None = None
    application_email: str | None = Field(default=None, max_length=255)
    valid_through: date | None = None
    status: JobStatus = JobStatus.DRAFT
    visa_sponsorship: bool | None = None
    relocation_assistance: bool | None = None

    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    @model_validator(mode="after")
    def _salary_range(self) -> JobSummary:
        """The aggregate's invariant, on the projection of it: a row cannot say 80k-60k."""
        _salary_range_is_ordered(self.salary_min, self.salary_max)
        return self

    @field_serializer("salary_min", "salary_max", when_used="json")
    def _plain_salary(self, value: Decimal | None) -> Decimal | None:
        return plain_salary(value)
