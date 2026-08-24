"""Query helpers shared by the job board repositories."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def _count(session: AsyncSession, stmt: Select) -> int:
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return int(total or 0)
