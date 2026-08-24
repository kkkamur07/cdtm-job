from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.mapping import dump_for_db
from backend.members.application.commands import EntryUpsert, IntentsUpsert
from backend.members.domain import MemberEntry, MemberIntents
from backend.members.infrastructure._mappers import build_search_text
from backend.members.infrastructure.orm_models import MemberEntryRow, MemberIntentsRow, MemberRow
from infrastructure.repository import run_db, utc_now


class SqlEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, member_id: UUID) -> MemberEntry | None:
        row = await run_db(
            "entries.get", lambda: self._s.get(MemberEntryRow, member_id), session=self._s
        )
        return MemberEntry.model_validate(row) if row else None

    async def upsert(self, member_id: UUID, payload: EntryUpsert) -> MemberEntry:
        async def go() -> MemberEntry:
            row = await self._s.get(MemberEntryRow, member_id)
            if row is None:
                row = MemberEntryRow(member_id=member_id)
                self._s.add(row)
            for k, v in dump_for_db(payload, exclude_unset=True).items():
                setattr(row, k, v.value if hasattr(v, "value") else v)
            row.updated_at = utc_now()
            await self._s.flush()
            member = await self._s.get(MemberRow, member_id)
            if member is not None:
                await self._s.refresh(member)
                member.search_text = build_search_text(member)
                member.updated_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return MemberEntry.model_validate(row)

        return await run_db("entries.upsert", go, session=self._s)

    async def get_intents(self, member_id: UUID) -> MemberIntents | None:
        row = await run_db(
            "intents.get", lambda: self._s.get(MemberIntentsRow, member_id), session=self._s
        )
        return MemberIntents.model_validate(row) if row else None

    async def upsert_intents(self, member_id: UUID, payload: IntentsUpsert) -> MemberIntents:
        async def go() -> MemberIntents:
            row = await self._s.get(MemberIntentsRow, member_id)
            if row is None:
                row = MemberIntentsRow(member_id=member_id)
                self._s.add(row)
            for k, v in dump_for_db(payload, exclude_unset=True).items():
                setattr(row, k, v)
            row.updated_at = utc_now()
            await self._s.commit()
            await self._s.refresh(row)
            return MemberIntents.model_validate(row)

        return await run_db("intents.upsert", go, session=self._s)
