"""Supabase-backed seeker repository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from supabase import Client

from backend.core.page import PageResult
from backend.core.errors import supabase_execute
from backend.seekers.domain.seeker import Seeker
from backend.seekers.services.commands import SeekerCreate, SeekerUpdate


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SupabaseSeekerRepository:
    _table = "seekers"

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(self, *, skip: int, limit: int) -> PageResult[Seeker]:
        res = supabase_execute(
            "seekers.list",
            lambda: self._client.table(self._table)
            .select("*", count="exact")
            .order("created_at", desc=True)
            .range(skip, skip + limit - 1)
            .execute(),
        )
        rows = res.data or []
        total = int(res.count) if res.count is not None else len(rows)
        return PageResult(items=[Seeker.model_validate(r) for r in rows], total=total)

    def get(self, seeker_id: UUID) -> Seeker | None:
        res = supabase_execute(
            "seekers.get",
            lambda: self._client.table(self._table)
            .select("*")
            .eq("id", str(seeker_id))
            .limit(1)
            .execute(),
        )
        if not res.data:
            return None
        return Seeker.model_validate(res.data[0])

    def create(self, payload: SeekerCreate) -> Seeker:
        now = _utc_now()
        new_id = uuid4()
        row = {
            "id": str(new_id),
            **payload.model_dump(mode="json"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        res = supabase_execute(
            "seekers.create",
            lambda: self._client.table(self._table).insert(row).select("*").single().execute(),
        )
        return Seeker.model_validate(res.data)

    def update(self, seeker_id: UUID, payload: SeekerUpdate) -> Seeker | None:
        patch = payload.model_dump(exclude_unset=True, mode="json")
        if not patch:
            return self.get(seeker_id)
        res = supabase_execute(
            "seekers.update",
            lambda: self._client.table(self._table)
            .update(patch)
            .eq("id", str(seeker_id))
            .select("*")
            .single()
            .execute(),
        )
        if res.data is None:
            return None
        return Seeker.model_validate(res.data)

    def delete(self, seeker_id: UUID) -> bool:
        res = supabase_execute(
            "seekers.delete",
            lambda: self._client.table(self._table)
            .delete()
            .eq("id", str(seeker_id))
            .select("id")
            .execute(),
        )
        return bool(res.data)
