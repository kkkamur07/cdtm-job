"""Public API models for companies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.companies.domain.company import Company


class CompanyPublic(Company):
    """Response body for a single company."""

    model_config = ConfigDict(title="CompanyPublic")


class CompaniesPublic(BaseModel):
    """Paginated company list."""

    model_config = ConfigDict(extra="forbid")

    items: list[CompanyPublic]
    total: int
