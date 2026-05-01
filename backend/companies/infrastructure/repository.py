"""Supabase-backed company repository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from supabase import Client

from backend.companies.domain.company import Company
from backend.companies.services.commands import CompanyCreate, CompanyUpdate
from backend.core.page import PageResult
from backend.core.errors import RepositoryError, supabase_execute


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SupabaseCompanyRepository:
    _table = "companies"

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(self, *, skip: int, limit: int) -> PageResult[Company]:
        res = supabase_execute(
            "companies.list",
            lambda: self._client.table(self._table)
            .select("*", count="exact")
            .order("created_at", desc=True)
            .range(skip, skip + limit - 1)
            .execute(),
        )
        rows = res.data or []
        total = int(res.count) if res.count is not None else len(rows)
        return PageResult(items=[Company.model_validate(r) for r in rows], total=total)

    def get(self, company_id: UUID) -> Company | None:
        res = supabase_execute(
            "companies.get",
            lambda: self._client.table(self._table)
            .select("*")
            .eq("id", str(company_id))
            .limit(1)
            .execute(),
        )
        if not res.data:
            return None
        return Company.model_validate(res.data[0])

    def get_by_slug(self, slug: str) -> Company | None:
        res = supabase_execute(
            "companies.get_by_slug",
            lambda: self._client.table(self._table).select("*").eq("slug", slug).limit(1).execute(),
        )
        if not res.data:
            return None
        return Company.model_validate(res.data[0])

    def create(self, payload: CompanyCreate) -> Company:
        now = _utc_now()
        new_id = uuid4()
        row = {
            "id": str(new_id),
            **payload.model_dump(mode="json"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        res = supabase_execute(
            "companies.create",
            lambda: self._client.table(self._table).insert(row).execute(),
        )
        rows = res.data or []
        if not rows:
            raise RepositoryError("companies.create: empty response")
        return Company.model_validate(rows[0])

    def update(self, company_id: UUID, payload: CompanyUpdate) -> Company | None:
        patch = payload.model_dump(exclude_unset=True, mode="json")
        if not patch:
            return self.get(company_id)
        res = supabase_execute(
            "companies.update",
            lambda: self._client.table(self._table)
            .update(patch)
            .eq("id", str(company_id))
            .execute(),
        )
        rows = res.data or []
        if not rows:
            return None
        return Company.model_validate(rows[0])

    def delete(self, company_id: UUID) -> bool:
        res = supabase_execute(
            "companies.delete",
            lambda: self._client.table(self._table).delete().eq("id", str(company_id)).execute(),
        )
        return bool(res.data)
