"""Write models for the members context."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.members.domain import (
    CaDetail,
    ContactPreference,
    Education,
    MatchMethod,
    Position,
    Role,
    Visibility,
)

# ---- self-service profile --------------------------------------------------------------


class SelfProfileCreate(BaseModel):
    """The profile a signed-in account fills in when no roster row matched its e-mail.

    Only what a person can honestly say about themselves on day one: their name, which
    batch they belong to, and their study. Everything a scrape would add (positions,
    educations, skills) is left for a later edit rather than invented here. The avatar and
    e-mail are not on the form: they come from the Google account that is claiming the
    profile, so they cannot be spoofed to look like someone else.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    #: The class this member belongs to, chosen from ``GET /members/classes``. Its label is
    #: resolved server-side so the card and the class filter agree.
    class_id: int
    major: str = Field(min_length=1, max_length=160)
    headline: str | None = Field(default=None, max_length=200)
    current_company: str | None = Field(default=None, max_length=160)
    current_title: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    linkedin_url: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=2000)


# ---- entry & intents -------------------------------------------------------------------


class EntryUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ask_me_about: str | None = Field(default=None, max_length=500)
    about: str | None = Field(default=None, max_length=2000)
    current_title: str | None = Field(default=None, max_length=160)
    current_company: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    contact_preference: ContactPreference | None = None
    contact_email: str | None = Field(default=None, max_length=255)
    hobbies: list[str] | None = Field(default=None, max_length=20)
    topics: list[str] | None = Field(default=None, max_length=20)
    visibility: Visibility | None = None


class IntentsUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cofounding: bool | None = None
    mentoring: bool | None = None
    hiring: bool | None = None
    open_to_roles: bool | None = None
    speaking: bool | None = None
    investing: bool | None = None
    note: str | None = Field(default=None, max_length=280)


# ---- import (loader) --------------------------------------------------------------------


class ClassImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    label: str
    season: str | None = None
    year: int
    location: int | None = None


class MemberImport(BaseModel):
    """One member as produced by ``ingest.mjs`` (index tile + profile json merged)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    roster_person_id: int | None = None
    name: str
    first_name: str | None = None
    last_name: str | None = None
    roster_name: str | None = None
    email: str | None = None
    headline: str | None = None
    summary: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    avatar_sm_url: str | None = None
    avatar_lg_url: str | None = None
    avatar_blur: str | None = None
    class_ids: list[int] = Field(default_factory=list)
    class_label: str | None = None
    major: str | None = None
    roles: list[Role] = Field(default_factory=list)
    is_ca: bool = False
    ca_alumni: bool | None = None
    matched: bool = False
    match_method: MatchMethod | None = None
    needs_review: bool = False
    current_company: str | None = None
    current_title: str | None = None
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    company_info: dict | None = None
    ca: CaDetail | None = None
    positions: list[Position] = Field(default_factory=list)
    educations: list[Education] = Field(default_factory=list)
    linkedin_synced_at: datetime | None = None
