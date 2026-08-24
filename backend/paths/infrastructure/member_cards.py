"""Names and faces for the ids in a group, so a box of the Sankey opens into people.

A ``MemberCard`` is not a second model of a Member: it is the thirteen columns this
context needs to draw somebody, read out of the member tables without importing them. The
full profile stays one call away at ``GET /api/v1/members/{slug}``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.paths.domain import MemberCard
from backend.paths.infrastructure._member_tables import members
from infrastructure.repository import run_db

_CARD_COLUMNS = (
    members.c.id,
    members.c.slug,
    members.c.name,
    members.c.headline,
    members.c.avatar_sm_url,
    members.c.avatar_lg_url,
    members.c.avatar_blur,
    members.c.location,
    members.c.class_label,
    members.c.major,
    members.c.current_company,
    members.c.current_title,
    members.c.is_ca,
)


class SqlMemberCards:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def find_id_by_slug(self, slug: str) -> UUID | None:
        return await run_db(
            "paths.member_id_by_slug",
            lambda: self._s.scalar(select(members.c.id).where(members.c.slug == slug)),
            session=self._s,
        )

    async def cards(self, ids: list[UUID]) -> list[MemberCard]:
        """The cards for exactly these ids, alphabetical.

        The page was already cut by ``member_ids_page``, in this same order, so the ``IN``
        list here is the length of one page rather than the length of a career group. It
        orders again because a set of ids has no order of its own coming back out of
        Postgres, and the tie-break matches the one the page was cut with.
        """
        if not ids:
            return []

        async def go() -> list[MemberCard]:
            rows = (
                await self._s.execute(
                    select(*_CARD_COLUMNS)
                    .where(members.c.id.in_(ids))
                    .order_by(members.c.name, members.c.id)
                )
            ).all()
            return [
                MemberCard(
                    id=r[0],
                    slug=r[1],
                    name=r[2],
                    headline=r[3],
                    avatar_sm_url=r[4],
                    avatar_lg_url=r[5],
                    avatar_blur=r[6],
                    location=r[7],
                    class_label=r[8],
                    major=r[9],
                    company=r[10],
                    title=r[11],
                    is_ca=bool(r[12]),
                )
                for r in rows
            ]

        return await run_db("paths.member_cards", go, session=self._s)
