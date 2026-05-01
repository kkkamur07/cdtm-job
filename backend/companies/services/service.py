"""Company application service — CRUD orchestration."""

from __future__ import annotations

from uuid import UUID

from backend.companies.domain.company import Company
from backend.companies.services.commands import CompanyCreate, CompanyUpdate
from backend.companies.services.ports import CompanyRepository
from backend.core.errors import NotFoundError
from backend.core.page import PageResult


class CompanyService:
    def __init__(self, repo: CompanyRepository) -> None:
        self._repo = repo

    def list_companies(self, *, skip: int = 0, limit: int = 50) -> PageResult[Company]:
        skip = max(skip, 0)
        limit = min(max(limit, 1), 100)
        return self._repo.list(skip=skip, limit=limit)

    def get_company(self, company_id: UUID) -> Company:
        row = self._repo.get(company_id)
        if row is None:
            raise NotFoundError(f"Company {company_id} not found")
        return row

    def get_company_by_slug(self, slug: str) -> Company:
        row = self._repo.get_by_slug(slug)
        if row is None:
            raise NotFoundError(f"Company slug {slug!r} not found")
        return row

    def create_company(self, payload: CompanyCreate) -> Company:
        return self._repo.create(payload)

    def update_company(self, company_id: UUID, payload: CompanyUpdate) -> Company:
        row = self._repo.update(company_id, payload)
        if row is None:
            raise NotFoundError(f"Company {company_id} not found")
        return row

    def delete_company(self, company_id: UUID) -> None:
        if not self._repo.delete(company_id):
            raise NotFoundError(f"Company {company_id} not found")
