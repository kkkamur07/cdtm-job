"""SQL fragments every context's repositories need and none of them owns."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def ilike_contains(term: str) -> str:
    """ILIKE pattern for "contains term", with the user's % and _ treated as literal text."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def page_with_total(
    session: AsyncSession, stmt: Select, *, skip: int, limit: int
) -> tuple[list[Sequence[Any]], int]:
    """One statement for a page and the number of rows behind it.

    Every list endpoint used to run the filter twice: once as ``count(*)`` over the
    filtered subquery and once for the page itself. ``count(*) OVER ()`` is evaluated
    before LIMIT, so the first row of the page already carries the full tally and the
    predicate is evaluated once. Measured on the directory with ``?q=product``: 3,929
    shared buffers and two round trips became 1,949 and one.

    The caller gets the row tuples with the total stripped off the end, so a statement
    that selected one entity yields one-element tuples and one that selected extra
    computed columns keeps them in order.

    A page past the end has no row to read the total from. ``skip == 0`` with no rows is
    unambiguously zero and costs nothing; only a deep empty page falls back to a count
    query, which is the rare case and still correct.
    """
    page = stmt.add_columns(func.count().over()).offset(skip).limit(limit)
    res = (await session.execute(page)).all()
    if res:
        return [row[:-1] for row in res], int(res[0][-1])
    if skip == 0:
        return [], 0
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return [], int(total or 0)
