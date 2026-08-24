"""SQLAlchemy implementation of the seeker persistence port."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mapping import dump_for_db
from backend.core.page import PageResult
from backend.core.sql import page_with_total
from backend.jobboard.application.commands import (
    SeekerCreate,
    SeekerUpdate,
)
from backend.jobboard.domain import Seeker
from backend.jobboard.infrastructure.orm_models import SeekerRow
from infrastructure.repository import run_db, utc_now


class SqlSeekerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list(self, *, skip: int, limit: int) -> PageResult[Seeker]:
        async def go() -> PageResult[Seeker]:
            base = select(SeekerRow)
            rows, total = await page_with_total(
                self._s, base.order_by(SeekerRow.created_at.desc()), skip=skip, limit=limit
            )
            return PageResult(items=[Seeker.model_validate(r[0]) for r in rows], total=total)

        return await run_db("seekers.list", go, session=self._s)

    async def get(self, seeker_id: UUID) -> Seeker | None:
        row = await run_db(
            "seekers.get", lambda: self._s.get(SeekerRow, seeker_id), session=self._s
        )
        return Seeker.model_validate(row) if row else None

    async def create(self, payload: SeekerCreate, *, member_id: UUID | None) -> Seeker:
        async def go() -> Seeker:
            row = SeekerRow(**dump_for_db(payload), member_id=member_id)
            self._s.add(row)
            await self._s.commit()
            await self._s.refresh(row)
            return Seeker.model_validate(row)

        return await run_db("seekers.create", go, session=self._s)

    async def update(self, seeker_id: UUID, payload: SeekerUpdate) -> Seeker | None:
        async def go() -> Seeker | None:
            row = await self._s.get(SeekerRow, seeker_id)
            if row is None:
                return None
            patch = dump_for_db(payload, exclude_unset=True)
            if patch:
                for k, v in patch.items():
                    setattr(row, k, v)
                row.updated_at = utc_now()
                await self._s.commit()
                await self._s.refresh(row)
            return Seeker.model_validate(row)

        return await run_db("seekers.update", go, session=self._s)

    async def delete(self, seeker_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(delete(SeekerRow).where(SeekerRow.id == seeker_id))
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("seekers.delete", go, session=self._s)
