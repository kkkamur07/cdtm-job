from typing import Any
from uuid import UUID

from companies.application.commands import CreateCompanyCommand, UpdateCompanyCommand
from companies.infrastructure.repository import SupabaseCompanyRepository


class CompanyService:
    def __init__(self, repository: SupabaseCompanyRepository) -> None:
        self._repository = repository

    def create_company(self, command: CreateCompanyCommand) -> UUID:
        return self._repository.insert_company(command)

    def update_company(self, company_id: UUID, command: UpdateCompanyCommand) -> None:
        self._repository.update_company(company_id, command)

    def delete_company(self, company_id: UUID) -> bool:
        return self._repository.delete_company(company_id)

    def get_company_by_slug(self, slug: str) -> dict[str, Any] | None:
        return self._repository.get_by_slug(slug)

    def get_company(self, company_id: UUID) -> dict[str, Any] | None:
        return self._repository.get_by_id(company_id)

    def list_companies(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._repository.list_companies(limit=limit)
