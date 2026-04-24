"""Input models (“commands”) for job use cases.

**Why separate “commands”?**
- They are **validated input DTOs** (Pydantic) for a single operation (create, update).
- Keeping them out of HTTP routers and out of the domain keeps **transport**, **validation**,
  and **business meaning** separate: routers parse HTTP → commands; application services
  accept commands; infrastructure maps to rows.
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobLocationIn(BaseModel):
    label: str = Field(min_length=1)
    is_primary: bool = False
    country_code: str | None = Field(default=None, max_length=2)
    city: str | None = None
    sort_order: int = 0


class CreateJobCommand(BaseModel):
    """Validated payload for creating a job and its locations."""

    company_id: UUID
    title: str = Field(min_length=1)
    slug: str = Field(min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1)
    summary: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    department: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    application_url: str | None = None
    application_email: str | None = None
    visa_sponsorship: bool | None = None
    status: str = Field(default="draft", pattern=r"^(draft|published|closed)$")
    locations: list[JobLocationIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_locations_and_salary(self) -> "CreateJobCommand":
        if not self.locations:
            raise ValueError("At least one location is required")
        if self.status == "published" and not any(loc.is_primary for loc in self.locations):
            raise ValueError("Published jobs require one primary location (is_primary=true)")
        if (self.salary_min is not None or self.salary_max is not None) and not self.salary_currency:
            raise ValueError("salary_currency is required when salary bounds are set")
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("salary_min cannot be greater than salary_max")
        return self


class UpdateJobCommand(BaseModel):
    """Partial update: only set fields are written; `locations` replaces all rows when provided."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    department: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    application_url: str | None = None
    application_email: str | None = None
    visa_sponsorship: bool | None = None
    status: str | None = Field(default=None, pattern=r"^(draft|published|closed)$")
    locations: list[JobLocationIn] | None = None

    @model_validator(mode="after")
    def validate_when_present(self) -> "UpdateJobCommand":
        if self.locations is not None:
            if not self.locations:
                raise ValueError("When provided, locations must contain at least one entry")
            if not any(loc.is_primary for loc in self.locations):
                raise ValueError("At least one location must have is_primary=true")
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("salary_min cannot be greater than salary_max")
        return self
