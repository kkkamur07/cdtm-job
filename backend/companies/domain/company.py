"""Company aggregate — branding, classification, HQ, audit."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CompanySizeBand(StrEnum):
    STARTUP = "startup"
    SMB = "smb"
    MID = "mid"
    ENTERPRISE = "enterprise"


class Company(BaseModel):
    """Employer organization surfaced on the job board."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)
    legal_name: str | None = Field(default=None, max_length=255)

    logo_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    careers_page_url: HttpUrl | None = None

    short_description: str | None = Field(default=None, max_length=512)
    full_description: str | None = None

    industry: str | None = Field(default=None, max_length=128)
    company_size_band: CompanySizeBand | None = None
    is_cdtm_startup: bool = False

    hq_city: str | None = Field(default=None, max_length=128)
    hq_region: str | None = Field(default=None, max_length=128)
    hq_country: str | None = Field(default=None, max_length=128)

    linkedin_url: HttpUrl | None = None
    twitter_url: HttpUrl | None = None

    created_at: datetime
    updated_at: datetime
