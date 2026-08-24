"""Read-only lookup of members by e-mail or slug, used to bind accounts (raw SQL so identity does not import community's ORM)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.identity.domain import MemberSummary
from infrastructure.repository import run_db, utc_now

_SUMMARY_COLUMNS = "id, slug, name, email, class_label"


class SqlMemberDirectory:
    """Minimal read into ``members`` so identity does not import community's ORM."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def find_member_id_by_email(self, email: str) -> UUID | None:
        return await run_db(
            "members.find_by_email",
            lambda: self._s.scalar(
                text("select id from members where lower(email) = :email limit 1"),
                {"email": email.lower()},
            ),
            session=self._s,
        )

    async def find_member_id_by_slug(self, slug: str) -> UUID | None:
        return await run_db(
            "members.find_by_slug",
            lambda: self._s.scalar(
                text("select id from members where slug = :slug limit 1"), {"slug": slug}
            ),
            session=self._s,
        )

    async def find_member_slug_by_id(self, member_id: UUID) -> str | None:
        return await run_db(
            "members.find_slug_by_id",
            lambda: self._s.scalar(
                text("select slug from members where id = :id"), {"id": member_id}
            ),
            session=self._s,
        )

    async def get_member_by_slug(self, slug: str) -> MemberSummary | None:
        async def go() -> MemberSummary | None:
            result = await self._s.execute(
                text(f"select {_SUMMARY_COLUMNS} from members where slug = :slug"),  # noqa: S608
                {"slug": slug},
            )
            row = result.mappings().first()
            return MemberSummary.model_validate(dict(row)) if row else None

        return await run_db("members.get_by_slug", go, session=self._s)

    async def set_member_email(self, member_id: UUID, email: str) -> None:
        """Development login only. Fills in the Workspace e-mail a roster row is missing.

        ``members.email`` is unique on ``lower(email)``, so a clash surfaces as the usual 409
        out of ``run_db`` rather than as a silent overwrite.
        """

        async def go() -> None:
            await self._s.execute(
                text("update members set email = :email, updated_at = :now where id = :id"),
                {"email": email.lower(), "now": utc_now(), "id": member_id},
            )
            await self._s.commit()

        await run_db("members.set_email", go, session=self._s)

    async def search_members(self, query: str | None, *, limit: int) -> list[MemberSummary]:
        async def go() -> list[MemberSummary]:
            sql = f"select {_SUMMARY_COLUMNS} from members"  # noqa: S608
            params: dict[str, object] = {"limit": limit}
            if query:
                sql += " where name ilike :q or slug ilike :q"
                params["q"] = f"%{query}%"
            sql += " order by name limit :limit"
            result = await self._s.execute(text(sql), params)
            return [MemberSummary.model_validate(dict(r)) for r in result.mappings().all()]

        return await run_db("members.search", go, session=self._s)
