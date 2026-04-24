"""Validated commands for company use cases."""

from pydantic import BaseModel, ConfigDict, Field


class CreateCompanyCommand(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    headquarters_location: str | None = None
    company_size_band: str | None = None
    industry: str | None = None
    is_cdtm_startup: bool = Field(
        default=False,
        description="Maps to DB column _is_cdtm_startup (CDTM vs external label).",
    )


class UpdateCompanyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    headquarters_location: str | None = None
    company_size_band: str | None = None
    industry: str | None = None
    is_cdtm_startup: bool | None = None
