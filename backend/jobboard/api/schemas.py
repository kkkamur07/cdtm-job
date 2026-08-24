"""Public response models. Same shapes the original job board shipped."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.llm.ask import LANGUAGE_PATTERN
from backend.jobboard.domain import (
    MAX_ASK_LIMIT,
    Company,
    Job,
    JobAskAnswer,
    JobAskInterpretation,
    Seeker,
)


class CompanyPublic(Company):
    model_config = ConfigDict(title="CompanyPublic")


class CompaniesPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CompanyPublic]
    total: int


class JobPublic(Job):
    model_config = ConfigDict(title="JobPublic")


class JobsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[JobPublic]
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
    model_config = ConfigDict(title="JobAskInterpretationPublic")


class JobAskAnswerPublic(JobAskAnswer):
    model_config = ConfigDict(title="JobAskAnswerPublic")


class JobAskSchemaPublic(BaseModel):
    """The filter object the UI renders chips from, and the values those chips may take."""

    model_config = ConfigDict(extra="forbid")

    json_schema: dict[str, Any]
    employment_types: list[str]
    work_arrangements: list[str]
    experience_levels: list[str]
    sorts: list[str]
    max_limit: int = MAX_ASK_LIMIT
