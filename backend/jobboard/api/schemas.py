"""Public response models. Same shapes the original job board shipped."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer

from backend.core.llm.ask import LANGUAGE_PATTERN
from backend.jobboard.domain import (
    MAX_ASK_LIMIT,
    Company,
    CompensationDisclosure,
    EmploymentType,
    ExperienceLevel,
    Job,
    JobAskAnswer,
    JobAskInterpretation,
    JobStatus,
    SalaryPeriod,
    Seeker,
    WorkArrangement,
)


class CompanyPublic(Company):
    model_config = ConfigDict(title="CompanyPublic")


class CompaniesPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CompanyPublic]
    total: int


class JobPublic(Job):
    model_config = ConfigDict(title="JobPublic")


class JobSummaryPublic(BaseModel):
    """A job as a list row: everything the board draws, and none of the long text.

    ``JobPublic`` is the whole aggregate, and one of its fields (``description``) may be
    twenty thousand characters. A hundred of those on ``GET /jobs/`` is a megabyte of JSON
    nothing on the page reads: the rows draw a title, a company, three badges, a location,
    a salary and a date. The three skill and language lists go the same way. Opening a
    listing still answers with the whole aggregate, which is where the description belongs.

    The fields below are copied from ``Job`` rather than inherited, because pydantic has no
    way to take a field back off a parent. ``tests/unit/test_list_summary_dtos.py`` pins the
    two field sets against each other, so a field added to the aggregate cannot go missing
    from the board without a test saying so.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True, title="JobSummaryPublic")

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

    @field_serializer("salary_min", "salary_max", when_used="json")
    def _plain_salary(self, value: Decimal | None) -> Decimal | None:
        """The aggregate's own normalisation, so a row and the detail page never disagree."""
        return Job._plain_salary(self, value)


class JobsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[JobSummaryPublic]
    total: int


class SeekerPublic(Seeker):
    model_config = ConfigDict(title="SeekerPublic")


class SeekersPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SeekerPublic]
    total: int


# ---- ask -------------------------------------------------------------------------------


#: Documented once, used on both Ask request bodies here. The members and housing boards
#: say the same thing in ``backend/core/schemas/ask.py``.
_LANGUAGE_HELP = (
    "BCP-47 tag the one-sentence summary should be written in. Omit it and the summary "
    "comes back in the language the question was asked in. Filters are unaffected."
)


class JobAskRequest(BaseModel):
    """A plain-words question, plus where in the answer to start."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=300)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=MAX_ASK_LIMIT)
    language: str | None = Field(
        default=None, max_length=16, pattern=LANGUAGE_PATTERN, description=_LANGUAGE_HELP
    )


class JobAskExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=300)
    language: str | None = Field(
        default=None, max_length=16, pattern=LANGUAGE_PATTERN, description=_LANGUAGE_HELP
    )


class JobAskInterpretationPublic(JobAskInterpretation):
    #: ``from_attributes`` so the router can validate the domain object itself instead of
    #: dumping it to a dict first and validating that.
    model_config = ConfigDict(from_attributes=True, title="JobAskInterpretationPublic")


class JobAskAnswerPublic(JobAskAnswer):
    """An answer is a list of rows, so it ships the same summary the board does."""

    model_config = ConfigDict(from_attributes=True, title="JobAskAnswerPublic")

    jobs: list[JobSummaryPublic] = Field(default_factory=list)


class JobAskSchemaPublic(BaseModel):
    """The filter object the UI renders chips from, and the values those chips may take."""

    model_config = ConfigDict(extra="forbid")

    json_schema: dict[str, Any]
    employment_types: list[str]
    work_arrangements: list[str]
    experience_levels: list[str]
    sorts: list[str]
    max_limit: int = MAX_ASK_LIMIT
