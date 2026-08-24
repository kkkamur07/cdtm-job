"""What the classifier needs about one person, and nothing more.

The member tables hold a lot about a position: a description, a company URL, a location, a
sort order. A path is decided by four of those fields and by nothing else, so this is what
``CareerHistorySource`` reads. Keeping it this narrow is also what keeps the classifier
honest: a rule cannot start depending on a field it was never given.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    company: str | None = None
    start_date: date | None = None
    is_current: bool = False


class StudyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school: str | None = None
    degree: str | None = None


class CareerHistory(BaseModel):
    """One member's jobs, degrees and class, as the classifier reads them."""

    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    major: str | None = None
    class_year: int | None = None
    class_season: str | None = None
    work: list[WorkEntry] = Field(default_factory=list)
    study: list[StudyEntry] = Field(default_factory=list)
