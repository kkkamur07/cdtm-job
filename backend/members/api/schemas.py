"""Public request and response models for the members API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.llm.ask import MAX_ASK_LIMIT
from backend.members.domain import (
    AskAnswer,
    AskInterpretation,
    ClassRef,
    CompanyContact,
    Member,
    MemberEntry,
    MemberIntents,
    MemberProfile,
)
from backend.paths.api.schemas import PathFlowPublic


class MemberPublic(Member):
    model_config = ConfigDict(title="MemberPublic")


class MembersPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MemberPublic]
    total: int


class CompanyContactPublic(CompanyContact):
    model_config = ConfigDict(title="CompanyContactPublic")

    member: MemberPublic


class CompanyContactsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompanyContactPublic]
    total: int


class MemberProfilePublic(MemberProfile):
    model_config = ConfigDict(title="MemberProfilePublic")


class ClassPublic(ClassRef):
    model_config = ConfigDict(title="ClassPublic")


class DirectoryFacets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classes: list[ClassPublic]
    majors: list[str]
    members_total: int


class EntryPublic(MemberEntry):
    model_config = ConfigDict(title="EntryPublic")


class IntentsPublic(MemberIntents):
    model_config = ConfigDict(title="IntentsPublic")


# ---- ask -------------------------------------------------------------------------------


class AskInterpretationPublic(AskInterpretation):
    model_config = ConfigDict(title="AskInterpretationPublic")


class AskAnswerPublic(AskAnswer):
    """An answer, plus the Paths picture of the people in it.

    The flow belongs to the paths context and is composed in ``api/ask.py``. Importing
    ``PathFlowPublic`` here is an API-layer import between two contexts, which is what an
    API layer is for: it is the one place a response may be assembled out of more than one
    board's models. Nothing under ``application/`` or ``domain/`` may do the same.
    """

    model_config = ConfigDict(title="AskAnswerPublic")

    flow: PathFlowPublic | None = None


class AskSchemaPublic(BaseModel):
    """The filter object the UI renders chips from, and the values those chips may take."""

    model_config = ConfigDict(extra="forbid")

    json_schema: dict[str, Any]
    study_groups: list[str]
    career_groups: list[str]
    intents: list[str]
    roles: list[str]
    sorts: list[str]
    max_limit: int = Field(default=MAX_ASK_LIMIT)
