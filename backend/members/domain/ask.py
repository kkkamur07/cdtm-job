"""Ask over the directory: a plain-words question about people, as a filter object.

The whole point of these models is that they are the only thing a language model is
allowed to produce. A question becomes a ``MemberQuery``, pydantic decides whether that
object is acceptable, and only then does the same repository search the ordinary directory
endpoint runs. There is no path from a sentence to SQL.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.llm.ask import MAX_ASK_LIMIT, QuestionSource
from backend.members.domain.member import Member, Role

MemberSort = Literal["relevance", "name", "class"]


class Intent(StrEnum):
    """The six things a Member can say they are open to, as filter values."""

    COFOUNDING = "cofounding"
    MENTORING = "mentoring"
    HIRING = "hiring"
    OPEN_TO_ROLES = "open_to_roles"
    SPEAKING = "speaking"
    INVESTING = "investing"


class MemberQuery(BaseModel):
    """The strict filter object a question is translated into.

    Every field is optional and every field maps to something the directory can already
    filter on cheaply. A translator that cannot map a phrase leaves the field unset and
    reports the phrase in ``AskInterpretation.unresolved`` rather than inventing a value.

    ``study_group``, ``first_step_group`` and ``current_group`` are plain strings, not
    enumerations. The names belong to the Paths read model, which this context has no
    words for: they arrive as data (see ``application/ports.py``), go into the prompt, and
    come back out to be matched against ``member_paths`` as text.
    """

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=200, description="free text over the haystack")
    school: str | None = Field(default=None, max_length=120, description="a university name")
    degree: str | None = Field(default=None, max_length=120, description="a degree or field")
    major: str | None = Field(default=None, max_length=120, description="the CDTM roster major")
    company: str | None = Field(default=None, max_length=120, description="where they are now")
    past_company: str | None = Field(
        default=None, max_length=120, description="somewhere they have worked before"
    )
    title: str | None = Field(default=None, max_length=120, description="a job title")
    location: str | None = Field(default=None, max_length=120, description="a city or country")
    class_label: str | None = Field(
        default=None, max_length=64, description="a class label such as 'Spring 2021'"
    )
    class_year_min: int | None = Field(default=None, ge=1998, le=2100)
    class_year_max: int | None = Field(default=None, ge=1998, le=2100)
    study_group: str | None = Field(default=None, max_length=64, description="what they studied")
    first_step_group: str | None = Field(
        default=None, max_length=64, description="the first career step after CDTM"
    )
    current_group: str | None = Field(default=None, max_length=64, description="where they are now")
    skills: list[str] | None = Field(default=None, max_length=10, description="any of these")
    languages: list[str] | None = Field(default=None, max_length=10, description="any of these")
    intents: list[Intent] | None = Field(
        default=None, max_length=6, description="all of these must be true"
    )
    roles: list[Role] | None = Field(default=None, max_length=3, description="any of these")
    is_ca: bool | None = Field(default=None, description="Center Assistants only")
    limit: int | None = Field(default=None, ge=1, le=MAX_ASK_LIMIT)
    sort: MemberSort | None = None

    @field_validator("limit", mode="before")
    @classmethod
    def _clamp_limit(cls, value: object) -> object:
        # A model that asks for 500 people meant "lots", not "fail the request".
        if isinstance(value, int) and not isinstance(value, bool):
            return max(1, min(value, MAX_ASK_LIMIT))
        return value

    @field_validator("skills", "languages", "intents", "roles", mode="after")
    @classmethod
    def _drop_empty_lists(cls, value: list | None) -> list | None:
        # An empty list from the model means "no opinion", which is what None means here.
        return value or None


class AskInterpretation(BaseModel):
    """How the question was read, in a form the UI can show as editable chips."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=300)
    filters: MemberQuery
    confidence: float = Field(ge=0.0, le=1.0)
    unresolved: list[str] = Field(default_factory=list)
    source: QuestionSource


class AskAnswer(BaseModel):
    """The people a question matched.

    There is no Sankey here. The Paths flow drawn over an answer is the Paths read model's
    picture of it, and ``backend/members/api/ask.py`` is where the two are put side by
    side; this context does not know what a flow is.
    """

    model_config = ConfigDict(extra="forbid")

    interpretation: AskInterpretation
    members: list[Member] = Field(default_factory=list)
    total: int = 0
