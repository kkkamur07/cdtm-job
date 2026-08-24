"""Application service: use-case orchestration for company."""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult
from backend.jobboard.application.commands import (
    CompanyCreate,
    CompanyUpdate,
)
from backend.jobboard.application.ports import (
    CompanyFilters,
    CompanyRepository,
)
from backend.jobboard.application.visibility import can_manage_company
from backend.jobboard.domain import Company


class CompanyService:
    def __init__(self, repo: CompanyRepository) -> None:
        self._repo = repo

    async def list_companies(
        self, *, skip: int = 0, limit: int = 50, filters: CompanyFilters | None = None
    ) -> PageResult[Company]:
        return await self._repo.list(skip=skip, limit=limit, filters=filters or CompanyFilters())

    async def get_company(self, company_id: UUID) -> Company:
        row = await self._repo.get(company_id)
        if row is None:
            raise NotFoundError(f"Company {company_id} not found")
        return row

    async def get_company_by_slug(self, slug: str) -> Company:
        row = await self._repo.get_by_slug(slug)
        if row is None:
            raise NotFoundError(f"Company slug {slug!r} not found")
        return row

    async def create_company(
        self, payload: CompanyCreate, *, created_by_member_id: UUID | None
    ) -> Company:
        """The curator is whoever is signed in. The body cannot carry a creator id at all."""
        return await self._repo.create(payload, created_by_member_id=created_by_member_id)

    async def update_company(
        self, actor: Actor, company_id: UUID, payload: CompanyUpdate
    ) -> Company:
        """A Company is a shared record, so whoever curated it may correct it, and so may
        an admin. Nobody else, or one member renames the employer every other posting on the
        board points at."""
        current = await self.get_company(company_id)
        if not can_manage_company(current, actor):
            raise ForbiddenError("only the member who added this company or an admin can edit it")
        row = await self._repo.update(company_id, payload)
        if row is None:
            raise NotFoundError(f"Company {company_id} not found")
        return row

    async def delete_company(self, actor: Actor, company_id: UUID) -> None:
        """Admin only. Deleting a Company cascades to every Job posted under it, and those
        belong to other people; taking the board apart is a moderation act, not an edit."""
        if not actor.is_admin:
            raise ForbiddenError("only an admin can delete a company")
        if not await self._repo.delete(company_id):
            raise NotFoundError(f"Company {company_id} not found")
