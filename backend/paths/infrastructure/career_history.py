"""Reading the jobs, degrees and class a path is computed from.

This is the seam between Paths and Members. It is deliberately one direction and read
only: nothing here writes to a member table, and nothing in members knows the classifier
exists. See ``_member_tables.py`` for why these are table handles rather than an import.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.paths.domain import CareerHistory, StudyEntry, WorkEntry
from backend.paths.infrastructure._member_tables import (
    classes,
    educations,
    member_classes,
    members,
    positions,
)
from infrastructure.repository import run_db

#: How many members are read into memory at a time by :meth:`iter_all`. The loader runs it
#: over the whole directory, and holding three thousand people's positions at once is the
#: kind of thing that works on a laptop and falls over on a small dyno.
_BATCH = 200


def _class_of(rows: list[tuple[int | None, str | None]]) -> tuple[int | None, str | None]:
    """The member's earliest class, which is the one a "first step after CDTM" is after."""
    dated = sorted((r for r in rows if r[0] is not None), key=lambda r: r[0] or 0)
    return dated[0] if dated else (None, None)


class SqlCareerHistorySource:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, member_id: UUID) -> CareerHistory | None:
        async def go() -> CareerHistory | None:
            row = (
                await self._s.execute(
                    select(members.c.id, members.c.major).where(members.c.id == member_id)
                )
            ).first()
            if row is None:
                return None
            histories = await self._load([member_id], {member_id: row[1]})
            return histories.get(member_id)

        return await run_db("paths.career_history", go, session=self._s)

    async def iter_all(self) -> AsyncIterator[CareerHistory]:
        """Every member, oldest id first, a batch at a time."""
        after: UUID | None = None
        while True:
            batch = await run_db(
                "paths.career_history_batch",
                lambda cursor=after: self._batch(cursor),
                session=self._s,
            )
            if not batch:
                return
            for history in batch:
                yield history
            after = batch[-1].member_id

    async def _batch(self, after: UUID | None) -> list[CareerHistory]:
        stmt = select(members.c.id, members.c.major).order_by(members.c.id).limit(_BATCH)
        if after is not None:
            stmt = stmt.where(members.c.id > after)
        page = (await self._s.execute(stmt)).all()
        if not page:
            return []
        majors = {row[0]: row[1] for row in page}
        histories = await self._load(list(majors), majors)
        return [histories[member_id] for member_id in majors]

    async def _load(
        self, ids: list[UUID], majors: dict[UUID, str | None]
    ) -> dict[UUID, CareerHistory]:
        work: dict[UUID, list[WorkEntry]] = {i: [] for i in ids}
        study: dict[UUID, list[StudyEntry]] = {i: [] for i in ids}
        cohort: dict[UUID, list[tuple[int | None, str | None]]] = {i: [] for i in ids}

        for row in (
            await self._s.execute(
                select(
                    positions.c.member_id,
                    positions.c.title,
                    positions.c.company,
                    positions.c.start_date,
                    positions.c.is_current,
                )
                .where(positions.c.member_id.in_(ids))
                .order_by(positions.c.member_id, positions.c.sort_order)
            )
        ).all():
            work[row[0]].append(
                WorkEntry(title=row[1], company=row[2], start_date=row[3], is_current=bool(row[4]))
            )

        for row in (
            await self._s.execute(
                select(educations.c.member_id, educations.c.school, educations.c.degree)
                .where(educations.c.member_id.in_(ids))
                .order_by(educations.c.member_id, educations.c.sort_order)
            )
        ).all():
            study[row[0]].append(StudyEntry(school=row[1], degree=row[2]))

        for row in (
            await self._s.execute(
                select(member_classes.c.member_id, classes.c.year, classes.c.season)
                .join(classes, classes.c.id == member_classes.c.class_id)
                .where(member_classes.c.member_id.in_(ids))
            )
        ).all():
            cohort[row[0]].append((row[1], row[2]))

        out: dict[UUID, CareerHistory] = {}
        for member_id in ids:
            year, season = _class_of(cohort[member_id])
            out[member_id] = CareerHistory(
                member_id=member_id,
                major=majors.get(member_id),
                class_year=year,
                class_season=season,
                work=work[member_id],
                study=study[member_id],
            )
        return out
