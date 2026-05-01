"""Persistence ports for companies."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.companies.domain.company import Company
from backend.companies.services.commands import CompanyCreate, CompanyUpdate
from backend.core.page import PageResult


class CompanyRepository(Protocol):
    def list(self, *, skip: int, limit: int) -> PageResult[Company]: ...

    def get(self, company_id: UUID) -> Company | None: ...

    def get_by_slug(self, slug: str) -> Company | None: ...

    def create(self, payload: CompanyCreate) -> Company: ...

    def update(self, company_id: UUID, payload: CompanyUpdate) -> Company | None: ...

    def delete(self, company_id: UUID) -> bool: ...
