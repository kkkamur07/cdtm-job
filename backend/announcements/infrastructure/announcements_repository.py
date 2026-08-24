from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.announcements.application.commands import AnnouncementCreate, AnnouncementUpdate
from backend.announcements.domain import Announcement
from backend.announcements.infrastructure.orm_models import AnnouncementReadRow, AnnouncementRow
from backend.core.mapping import dump_for_db
from backend.core.page import PageResult
from infrastructure.repository import run_db, utc_now


class SqlAnnouncementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _select(self, viewer: UUID | None) -> Select:
        reads = (
            select(func.count())
            .where(AnnouncementReadRow.announcement_id == AnnouncementRow.id)
            .correlate(AnnouncementRow)
            .scalar_subquery()
        )
        is_read = (
            exists().where(
                and_(
                    AnnouncementReadRow.announcement_id == AnnouncementRow.id,
                    AnnouncementReadRow.member_id == viewer,
                )
            )
            if viewer is not None
            else func.cast(False, AnnouncementRow.is_pinned.type)
        )
        return select(AnnouncementRow, reads.label("reads"), is_read.label("is_read"))

    @staticmethod
    def _to_domain(row: AnnouncementRow, reads: int, is_read: bool) -> Announcement:
        return Announcement(
            id=row.id,
            title=row.title,
            body=row.body,
            author_member_id=row.author_member_id,
            is_pinned=row.is_pinned,
            published_at=row.published_at,
            expires_at=row.expires_at,
            read_count=int(reads or 0),
            is_read=bool(is_read),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _visible() -> list:
        return [
            AnnouncementRow.published_at.is_not(None),
            AnnouncementRow.published_at <= func.now(),
            or_(AnnouncementRow.expires_at.is_(None), AnnouncementRow.expires_at > func.now()),
        ]

    async def list(
        self, *, skip: int, limit: int, viewer_member_id: UUID | None, include_unpublished: bool
    ) -> PageResult[Announcement]:
        async def go() -> PageResult[Announcement]:
            conds = [] if include_unpublished else self._visible()
            total = await self._s.scalar(select(func.count(AnnouncementRow.id)).where(*conds))
            res = await self._s.execute(
                self._select(viewer_member_id)
                .where(*conds)
                .order_by(
                    AnnouncementRow.is_pinned.desc(),
                    func.coalesce(AnnouncementRow.published_at, AnnouncementRow.created_at).desc(),
                )
                .offset(skip)
                .limit(limit)
            )
            return PageResult(
                items=[self._to_domain(r, n, ir) for r, n, ir in res.all()], total=int(total or 0)
            )

        return await run_db("announcements.list", go, session=self._s)

    async def get(
        self, announcement_id: UUID, viewer_member_id: UUID | None, *, include_hidden: bool = False
    ) -> Announcement | None:
        """One announcement, by default only if it is currently on the board.

        ``include_hidden`` is what an admin gets, and what this repository passes to itself
        after a write so that creating a future-dated or already-expired announcement still
        returns the row it just wrote.
        """

        async def go() -> Announcement | None:
            conds = [] if include_hidden else self._visible()
            res = await self._s.execute(
                self._select(viewer_member_id).where(AnnouncementRow.id == announcement_id, *conds)
            )
            row = res.first()
            return self._to_domain(*row) if row else None

        return await run_db("announcements.get", go, session=self._s)

    async def create(
        self, payload: AnnouncementCreate, author_member_id: UUID | None
    ) -> Announcement:
        async def go() -> Announcement:
            values = dump_for_db(payload)
            if "published_at" not in payload.model_fields_set:
                values["published_at"] = utc_now()
            row = AnnouncementRow(**values, author_member_id=author_member_id)
            self._s.add(row)
            await self._s.commit()
            return await self.get(  # type: ignore[return-value]
                row.id, author_member_id, include_hidden=True
            )

        return await run_db("announcements.create", go, session=self._s)

    async def update(
        self, announcement_id: UUID, payload: AnnouncementUpdate
    ) -> Announcement | None:
        async def go() -> Announcement | None:
            row = await self._s.get(AnnouncementRow, announcement_id)
            if row is None:
                return None
            for k, v in dump_for_db(payload, exclude_unset=True).items():
                setattr(row, k, v)
            row.updated_at = utc_now()
            await self._s.commit()
            return await self.get(announcement_id, None, include_hidden=True)

        return await run_db("announcements.update", go, session=self._s)

    async def delete(self, announcement_id: UUID) -> bool:
        async def go() -> bool:
            res = await self._s.execute(
                delete(AnnouncementRow).where(AnnouncementRow.id == announcement_id)
            )
            await self._s.commit()
            return bool(res.rowcount)

        return await run_db("announcements.delete", go, session=self._s)

    async def mark_read(self, announcement_id: UUID, member_id: UUID) -> None:
        async def go() -> None:
            if await self._s.get(AnnouncementReadRow, (announcement_id, member_id)) is None:
                self._s.add(
                    AnnouncementReadRow(announcement_id=announcement_id, member_id=member_id)
                )
                await self._s.commit()

        await run_db("announcements.mark_read", go, session=self._s)

    async def unread_count(self, member_id: UUID) -> int:
        async def go() -> int:
            read = exists().where(
                and_(
                    AnnouncementReadRow.announcement_id == AnnouncementRow.id,
                    AnnouncementReadRow.member_id == member_id,
                )
            )
            n = await self._s.scalar(
                select(func.count(AnnouncementRow.id)).where(*self._visible(), ~read)
            )
            return int(n or 0)

        return await run_db("announcements.unread", go, session=self._s)
