"""Career paths: where members studied, their first step after CDTM, where they are now."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudyGroup(StrEnum):
    """The coarse fields of study a Path can land in.

    The names are domain vocabulary: they are what the Paths view labels its columns and
    what a member picks from in an Ask chip. The keyword lists that decide which one a
    degree belongs to are a property of our scraped data, so they stay in
    ``infrastructure/paths_classifier.py``; ``tests/unit/test_paths_classifier.py`` keeps
    the two in step.
    """

    BUSINESS_MANAGEMENT = "Business & Management"
    COMPUTER_SCIENCE = "Computer Science"
    ENGINEERING = "Engineering"
    NATURAL_SCIENCES_MATH = "Natural Sciences & Math"
    MEDICINE_LIFE_SCIENCES = "Medicine & Life Sciences"
    LAW_SOCIAL_SCIENCES = "Law & Social Sciences"
    OTHER = "Other"


class CareerGroup(StrEnum):
    """The coarse career groups a first step or a current position can land in."""

    FOUNDER = "Founder"
    STARTUP = "Startup"
    CONSULTING = "Consulting"
    BIG_TECH = "Big Tech"
    VENTURE_CAPITAL = "Venture Capital"
    CORPORATE = "Corporate"
    PRODUCT_ENGINEERING = "Product & Engineering"
    RESEARCH_ACADEMIA = "Research & Academia"
    FINANCE_BANKING = "Finance & Banking"
    OTHER = "Other"


STUDY_GROUP_NAMES: tuple[str, ...] = tuple(g.value for g in StudyGroup)
CAREER_GROUP_NAMES: tuple[str, ...] = tuple(g.value for g in CareerGroup)

#: The four columns of the Sankey, in the order a career runs. The last one is not a
#: career step: it is what the member says they are open to now, which is where the
#: picture stops being history and becomes something you can act on.
STAGES: tuple[str, ...] = ("study", "first_step", "current", "intent")

#: The intent stage's boxes: the column in ``member_intents`` and the label the Sankey
#: draws. The labels are this context's display text, not the members context's ``Intent``
#: values, because they are read by a person off a chart rather than posted back as a
#: filter.
INTENT_GROUPS: tuple[tuple[str, str], ...] = (
    ("cofounding", "Co-founding"),
    ("mentoring", "Mentoring"),
    ("hiring", "Hiring"),
    ("open_to_roles", "Open to roles"),
    ("speaking", "Speaking"),
    ("investing", "Investing"),
)

#: Where a member with no intents set lands, so every current box's outflow adds up to the
#: number of people in it rather than quietly losing the ones who have not said anything.
NO_INTENT_GROUP = "Not stated"


class MemberPath(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    member_id: UUID
    study_group: str | None = None
    first_step_group: str | None = None
    first_step_title: str | None = None
    first_step_company: str | None = None
    current_group: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    computed_at: datetime | None = None


class PathNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str  # one of STAGES
    group: str
    count: int


class PathLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_stage: str
    source_group: str
    target_stage: str
    target_group: str
    count: int


class PathFlow(BaseModel):
    """Aggregate flow for the cdtm-paths style view."""

    model_config = ConfigDict(extra="forbid")

    members_counted: int
    nodes: list[PathNode] = Field(default_factory=list)
    links: list[PathLink] = Field(default_factory=list)
