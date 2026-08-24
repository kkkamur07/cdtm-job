"""Reading names and faces for the two member ids a saved row or an intro request holds.

The same seam ``identity`` uses to read ``members.email``: raw ``text()`` queries, no ORM
across the boundary (ADR 0007). A saved person is shown as a card, so a card is all this
context is allowed to know about them.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.network.domain import MemberCard
from infrastructure.repository import run_db

_EXISTS = text("select 1 from members where id = :id")

_CARDS = text(
    """
    select id, slug, name, headline, avatar_sm_url, avatar_lg_url, avatar_blur,
           location, class_label, major, current_company, current_title, is_ca
      from members
     where id = any(:ids)
    """
)


class SqlMemberDirectory:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def exists(self, member_id: UUID) -> bool:
        found = await run_db(
            "network.member_exists",
            lambda: self._s.scalar(_EXISTS, {"id": member_id}),
            session=self._s,
        )
        return found is not None

    async def cards(self, ids: list[UUID]) -> dict[UUID, MemberCard]:
        if not ids:
            return {}

        async def go() -> dict[UUID, MemberCard]:
            res = await self._s.execute(_CARDS, {"ids": list(dict.fromkeys(ids))})
            return {
                row[0]: MemberCard(
                    id=row[0],
                    slug=row[1],
                    name=row[2],
                    headline=row[3],
                    avatar_sm_url=row[4],
                    avatar_lg_url=row[5],
                    avatar_blur=row[6],
                    location=row[7],
                    class_label=row[8],
                    major=row[9],
                    company=row[10],
                    title=row[11],
                    is_ca=bool(row[12]),
                )
                for row in res
            }

        return await run_db("network.member_cards", go, session=self._s)
