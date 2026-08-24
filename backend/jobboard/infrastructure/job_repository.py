"""SQLAlchemy implementation of the job persistence port."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import Select, and_, delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mapping import dump_for_db
from backend.core.page import PageResult
from backend.jobboard.application.commands import (
    JobCreate,
    JobUpdate,
)
from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import Job, JobStatus
from backend.jobboard.infrastructure._query import _count
from backend.jobboard.infrastructure.orm_models import CompanyRow, JobRow
from infrastructure.repository import run_db, utc_now


def _contains(term: str) -> str:
    """ILIKE pattern for "contains term", with the user's % and _ treated as literal text."""
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _order_by(f: JobFilters) -> list:
    """Newest first is the board's default and stays the default.

    "salary" sorts on the advertised floor and puts postings with no salary last, because
    a job that does not say what it pays is not the cheapest one.
    """
    if f.sort == "salary":
        return [JobRow.salary_min.desc().nullslast(), JobRow.created_at.desc()]
    return [JobRow.created_at.desc()]


class SqlJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _apply(self, stmt: Select, f: JobFilters) -> Select:
        if f.company_id is not None:
            stmt = stmt.where(JobRow.company_id == f.company_id)
        if f.status is not None:
            stmt = stmt.where(JobRow.status == f.status.value)
        if f.employment_type is not None:
            stmt = stmt.where(JobRow.employment_type == f.employment_type.value)
        if f.work_arrangement is not None:
            stmt = stmt.where(JobRow.work_arrangement == f.work_arrangement.value)
        if f.employment_types:
            stmt = stmt.where(JobRow.employment_type.in_([e.value for e in f.employment_types]))
        if f.work_arrangements:
            stmt = stmt.where(JobRow.work_arrangement.in_([w.value for w in f.work_arrangements]))
        if f.experience_levels:
            stmt = stmt.where(JobRow.experience_level.in_([x.value for x in f.experience_levels]))
        if f.posted_by_member_id is not None:
            stmt = stmt.where(JobRow.posted_by_member_id == f.posted_by_member_id)
        if f.city:
            stmt = stmt.where(
                or_(
                    JobRow.city.ilike(_contains(f.city)),
                    JobRow.location_display.ilike(_contains(f.city)),
                )
            )
        if f.country:
            stmt = stmt.where(JobRow.country.ilike(_contains(f.country)))
        if f.remote_only:
            stmt = stmt.where(JobRow.work_arrangement == "remote")
        if f.salary_min is not None:
            # Compared against the posting's own ceiling: a 60-80k range clears a 70k floor.
            stmt = stmt.where(
                or_(JobRow.salary_max >= f.salary_min, JobRow.salary_min >= f.salary_min)
            )
        if f.posted_within_days is not None:
            since = utc_now() - timedelta(days=f.posted_within_days)
            # published_at is null for a draft, so this also keeps unpublished rows out.
            stmt = stmt.where(JobRow.published_at >= since)
        if f.company or f.is_cdtm_startup is not None:
            conditions = [CompanyRow.id == JobRow.company_id]
            if f.company:
                conditions.append(CompanyRow.name.ilike(_contains(f.company)))
            if f.is_cdtm_startup is not None:
                conditions.append(CompanyRow.is_cdtm_startup.is_(f.is_cdtm_startup))
            stmt = stmt.where(exists().where(and_(*conditions)))
        if f.q:
            pattern = _contains(f.q)
            stmt = stmt.where(
                or_(
                    JobRow.title.ilike(pattern),
                    JobRow.summary.ilike(pattern),
                    JobRow.description.ilike(pattern),
                    JobRow.location_display.ilike(pattern),
                )
            )
        return stmt

    async def list(self, *, skip: int, limit: int, filters: JobFilters) -> PageResult[Job]:
        async def go() -> PageResult[Job]:
            base = self._apply(select(JobRow), filters)
            total = await _count(self._s, base)
            rows = (
                await self._s.scalars(base.order_by(*_order_by(filters)).offset(skip).limit(limit))
            ).all()
            return PageResult(items=[Job.model_validate(r) for r in rows], total=total)

        return await run_db("jobs.list", go, session=self._s)

    async def get(self, job_id: UUID) -> Job | None:
        row = await run_db("jobs.get", lambda: self._s.get(JobRow, job_id), session=self._s)
        return Job.model_validate(row) if row else None

    async def get_by_slug(self, slug: str) -> Job | None:
        row = await run_db(
            "jobs.get_by_slug",
            lambda: self._s.scalar(select(JobRow).where(JobRow.slug == slug)),
            session=self._s,
        )
        return Job.model_validate(row) if row else None

    async def create(self, payload: JobCreate, *, posted_by_member_id: UUID | None) -> Job:
        async def go() -> Job:
            values = dump_for_db(payload)
            values["posted_by_member_id"] = posted_by_member_id
            if payload.status == JobStatus.PUBLISHED:
                values["published_at"] = utc_now()
            row = JobRow(**values)
            self._s.add(row)
            await self._s.commit()
            await self._s.refresh(row)
            return Job.model_validate(row)

        return await run_db("jobs.create", go, session=self._s)

    async def update(self, job_id: UUID, payload: JobUpdate) -> Job | None:
        async def go() -> Job | None:
            row = await self._s.get(JobRow, job_id)
            if row is None:
                return None
            patch = dump_for_db(payload, exclude_unset=True)
            target_status = payload.status.value if payload.status is not None else row.status
            # First publish always stamps published_at; an explicit null is treated as omitted
            # so a fresh publish never lands with published_at cleared.
            if (
                target_status == JobStatus.PUBLISHED.value
                and row.status != JobStatus.PUBLISHED.value
                and patch.get("published_at") is None
            ):
                patch["published_at"] = utc_now()
            if patch:
                for k, v in patch.items():
                    setattr(row, k, v)
                row.updated_at = utc_now()
                await self._s.commit()
                await self._s.refresh(row)
            return Job.model_validate(row)

        return await run_db("jobs.update", go, session=self._s)

    async def delete(self, job_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(delete(JobRow).where(JobRow.id == job_id))
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("jobs.delete", go, session=self._s)
