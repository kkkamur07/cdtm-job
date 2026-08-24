"""SQLAlchemy implementation of the company persistence port."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mapping import dump_for_db
from backend.core.page import PageResult
from backend.jobboard.application.commands import (
    CompanyCreate,
    CompanyUpdate,
)
from backend.jobboard.application.ports import CompanyFilters
from backend.jobboard.domain import Company
from backend.jobboard.infrastructure._query import _count
from backend.jobboard.infrastructure.orm_models import CompanyRow
from infrastructure.repository import run_db, utc_now


class SqlCompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _apply(self, stmt: Select, f: CompanyFilters) -> Select:
        if f.industry:
            stmt = stmt.where(CompanyRow.industry == f.industry)
        if f.is_cdtm_startup is not None:
            stmt = stmt.where(CompanyRow.is_cdtm_startup.is_(f.is_cdtm_startup))
        if f.hq_city:
            stmt = stmt.where(CompanyRow.hq_city.ilike(f"%{f.hq_city}%"))
        if f.q:
            pattern = f"%{f.q.strip()}%"
            stmt = stmt.where(
                or_(
                    CompanyRow.name.ilike(pattern),
                    CompanyRow.short_description.ilike(pattern),
                    CompanyRow.industry.ilike(pattern),
                )
            )
        return stmt

    async def list(self, *, skip: int, limit: int, filters: CompanyFilters) -> PageResult[Company]:
        async def go() -> PageResult[Company]:
            base = self._apply(select(CompanyRow), filters)
            total = await _count(self._s, base)
            rows = (
                await self._s.scalars(base.order_by(CompanyRow.name).offset(skip).limit(limit))
            ).all()
            return PageResult(items=[Company.model_validate(r) for r in rows], total=total)

        return await run_db("companies.list", go, session=self._s)

    async def get(self, company_id: UUID) -> Company | None:
        row = await run_db(
            "companies.get", lambda: self._s.get(CompanyRow, company_id), session=self._s
        )
        return Company.model_validate(row) if row else None

    async def get_by_slug(self, slug: str) -> Company | None:
        row = await run_db(
            "companies.get_by_slug",
            lambda: self._s.scalar(select(CompanyRow).where(CompanyRow.slug == slug)),
            session=self._s,
        )
        return Company.model_validate(row) if row else None

    async def create(self, payload: CompanyCreate, *, created_by_member_id: UUID | None) -> Company:
        async def go() -> Company:
            row = CompanyRow(**dump_for_db(payload), created_by_member_id=created_by_member_id)
            self._s.add(row)
            await self._s.commit()
            await self._s.refresh(row)
            return Company.model_validate(row)

        return await run_db("companies.create", go, session=self._s)

    async def update(self, company_id: UUID, payload: CompanyUpdate) -> Company | None:
        async def go() -> Company | None:
            row = await self._s.get(CompanyRow, company_id)
            if row is None:
                return None
            patch = dump_for_db(payload, exclude_unset=True)
            if patch:
                for k, v in patch.items():
                    setattr(row, k, v)
                row.updated_at = utc_now()
                await self._s.commit()
                await self._s.refresh(row)
            return Company.model_validate(row)

        return await run_db("companies.update", go, session=self._s)

    async def delete(self, company_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(delete(CompanyRow).where(CompanyRow.id == company_id))
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("companies.delete", go, session=self._s)
