"""Ask: a plain-words question about the board, as a filter object.

Same contract as the community side: a language model may fill in these fields and nothing
else, pydantic decides whether the result is acceptable, and the repository does the rest.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.jobboard.domain.job import (
    EmploymentType,
    ExperienceLevel,
    JobSummary,
    WorkArrangement,
)

MAX_ASK_LIMIT = 100

JobSort = Literal["relevance", "recent", "salary"]
QuestionSource = Literal["llm", "rules"]


class JobQuery(BaseModel):
    """The strict filter object a job question is translated into."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=200, description="free text over the posting")
    employment_type: list[EmploymentType] | None = Field(
        default=None, max_length=7, description="any of these"
    )
    work_arrangement: list[WorkArrangement] | None = Field(
        default=None, max_length=3, description="any of these"
    )
    experience_level: list[ExperienceLevel] | None = Field(
        default=None, max_length=5, description="any of these"
    )
    city: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    remote_only: bool | None = Field(default=None, description="only fully remote roles")
    company: str | None = Field(default=None, max_length=128, description="the hiring company")
    is_cdtm_startup: bool | None = Field(
        default=None, description="companies founded by CDTM members"
    )
    salary_min: Decimal | None = Field(
        default=None, ge=0, description="the floor, in the posting's own currency"
    )
    posted_within_days: int | None = Field(default=None, ge=1, le=365)
    limit: int | None = Field(default=None, ge=1, le=MAX_ASK_LIMIT)
    sort: JobSort | None = None

    @field_validator("limit", mode="before")
    @classmethod
    def _clamp_limit(cls, value: object) -> object:
        if isinstance(value, int) and not isinstance(value, bool):
            return max(1, min(value, MAX_ASK_LIMIT))
        return value

    @field_validator("employment_type", "work_arrangement", "experience_level", mode="after")
    @classmethod
    def _drop_empty_lists(cls, value: list | None) -> list | None:
        return value or None


class JobAskInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=300)
    filters: JobQuery
    confidence: float = Field(ge=0.0, le=1.0)
    unresolved: list[str] = Field(default_factory=list)
    source: QuestionSource


class JobAskAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpretation: JobAskInterpretation
    #: Rows, not postings: an answer is a way of listing the board, and the browser opens a
    #: result the same way it opens a row, so it is fed from the same summary query.
    jobs: list[JobSummary] = Field(default_factory=list)
    total: int = 0
