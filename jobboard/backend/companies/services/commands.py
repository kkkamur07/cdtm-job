"""Write models for companies (application layer)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.companies.domain.company import CompanySizeBand


class CompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=128)
    legal_name: str | None = Field(default=None, max_length=255)
    logo_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    careers_page_url: HttpUrl | None = None
    short_description: str | None = Field(default=None, max_length=512)
    full_description: str | None = None
    industry: str | None = Field(default=None, max_length=128)
    company_size_band: CompanySizeBand | None = None
    is_cdtm_startup: bool | None = None
    hq_city: str | None = Field(default=None, max_length=128)
    hq_region: str | None = Field(default=None, max_length=128)
    hq_country: str | None = Field(default=None, max_length=128)
    linkedin_url: HttpUrl | None = None
    twitter_url: HttpUrl | None = None
