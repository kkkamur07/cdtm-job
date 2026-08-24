"""Member aggregate: roster identity + LinkedIn-derived profile."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.members.domain.entry import MemberEntry, MemberIntents


class Role(StrEnum):
    STUDENT = "student"
    CA = "ca"
    FACULTY = "faculty"


class MatchMethod(StrEnum):
    OVERRIDE = "override"
    EXACT = "exact"
    VARIANT = "variant"
    FOLD = "fold"
    TRUNCATED_SURNAME = "truncated-surname"
    FIRSTNAME_PREFIX = "firstname-prefix"
    CLAIM_ELIMINATION = "claim-elimination"
    RANKED = "ranked"
    ARBITRARY = "arbitrary"


class ClassRef(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    label: str
    season: str | None = None
    year: int
    location: int | None = None


class Avatar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sm: str
    lg: str
    blur: str | None = None


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID | None = None
    title: str | None = None
    company: str | None = None
    company_url: str | None = None
    description: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    date_range: str | None = None
    is_current: bool = False
    sort_order: int = 0
    source: str = "linkedin"


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID | None = None
    school: str | None = None
    degree: str | None = None
    date_range: str | None = None
    sort_order: int = 0


class CaDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    alumni: bool = False
    about: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    research_fields: list[str] = Field(default_factory=list)
    email: str | None = None


class CompanyInfo(BaseModel):
    """LinkedIn company block for the member's current employer (denormalised)."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    tagline: str | None = None
    description: str | None = None
    industry: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    employee_count: int | None = None
    founded_year: int | None = None
    location: str | None = None
    specialities: list[str] = Field(default_factory=list)


class RosterMatch(BaseModel):
    """How confidently this member was bound to a Workspace mailbox.

    Loader bookkeeping, not member-facing: it says how sure the import was that a roster
    person and a directory tile are the same human. Only an admin sees it, and only on a
    profile, because the admin bind page is its one reader. ``roster_person_id`` is an id
    in a source system and never leaves the backend at all.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    matched: bool = False
    match_method: MatchMethod | None = None
    needs_review: bool = False


class Member(BaseModel):
    """Tile-sized member record (what the directory lists)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    slug: str
    name: str
    first_name: str | None = None
    last_name: str | None = None
    headline: str | None = None
    avatar: Avatar | None = None
    location: str | None = None
    linkedin_url: str | None = None
    classes: list[ClassRef] = Field(default_factory=list)
    class_label: str | None = None
    major: str | None = None
    roles: list[Role] = Field(default_factory=list)
    is_ca: bool = False
    ca_alumni: bool | None = None
    company: str | None = None
    title: str | None = None
    intents: MemberIntents | None = None
    is_claimed: bool = False
    updated_at: datetime | None = None


class CompanyContact(BaseModel):
    """One member you could ask about a company, and how many there are in total.

    The job board renders a company per row and wants "who inside CDTM works here". Asking
    that one company at a time is one request per row; this is the whole page in one.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    #: Echoed back exactly as it was asked for, so the caller can key its rows on it.
    company: str
    member: Member
    #: Everyone the same name matches, not just the one member returned.
    total: int


class MemberProfile(Member):
    """Full profile: fetched when a tile is opened."""

    roster_name: str | None = None
    email: str | None = None
    #: Admin-only; ``None`` for everyone else. See ``RosterMatch``.
    review: RosterMatch | None = None
    summary: str | None = None
    positions: list[Position] = Field(default_factory=list)
    educations: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    company_info: CompanyInfo | None = None
    ca: CaDetail | None = None
    entry: MemberEntry | None = None
    linkedin_synced_at: datetime | None = None
