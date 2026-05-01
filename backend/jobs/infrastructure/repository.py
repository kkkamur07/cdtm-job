"""Supabase-backed job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from supabase import Client

from backend.core.page import PageResult
from backend.core.errors import RepositoryError, supabase_execute
from backend.jobs.domain.job import Job, JobStatus
from backend.jobs.services.commands import JobCreate, JobUpdate


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SupabaseJobRepository:
    _table = "jobs"

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(
        self,
        *,
        skip: int,
        limit: int,
        company_id: UUID | None,
        status: JobStatus | None,
    ) -> PageResult[Job]:
        q = self._client.table(self._table).select("*", count="exact")
        if company_id is not None:
            q = q.eq("company_id", str(company_id))
        if status is not None:
            q = q.eq("status", status.value)

        res = supabase_execute(
            "jobs.list",
            lambda: q.order("created_at", desc=True).range(skip, skip + limit - 1).execute(),
        )
        rows = res.data or []
        total = int(res.count) if res.count is not None else len(rows)
        return PageResult(items=[Job.model_validate(r) for r in rows], total=total)

    def get(self, job_id: UUID) -> Job | None:
        res = supabase_execute(
            "jobs.get",
            lambda: self._client.table(self._table)
            .select("*")
            .eq("id", str(job_id))
            .limit(1)
            .execute(),
        )
        if not res.data:
            return None
        return Job.model_validate(res.data[0])

    def get_by_slug(self, slug: str) -> Job | None:
        res = supabase_execute(
            "jobs.get_by_slug",
            lambda: self._client.table(self._table).select("*").eq("slug", slug).limit(1).execute(),
        )
        if not res.data:
            return None
        return Job.model_validate(res.data[0])

    def create(self, payload: JobCreate) -> Job:
        now = _utc_now()
        new_id = uuid4()
        row = {
            "id": str(new_id),
            **payload.model_dump(mode="json"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        if payload.status == JobStatus.PUBLISHED:
            row["published_at"] = now.isoformat()
        res = supabase_execute(
            "jobs.create",
            lambda: self._client.table(self._table).insert(row).execute(),
        )
        rows = res.data or []
        if not rows:
            raise RepositoryError("jobs.create: empty response")
        return Job.model_validate(rows[0])

    def update(self, job_id: UUID, payload: JobUpdate) -> Job | None:
        existing = self.get(job_id)
        if existing is None:
            return None
        patch = payload.model_dump(exclude_unset=True, mode="json")
        target_status = payload.status if payload.status is not None else existing.status
        # First publish: always set a timestamp. Treat explicit null like omitted so we never
        # PATCH published_at=null onto a newly published row (would clear DB / hurt indexes).
        if (
            target_status == JobStatus.PUBLISHED
            and existing.status != JobStatus.PUBLISHED
            and patch.get("published_at") is None
        ):
            patch["published_at"] = _utc_now().isoformat()
        if not patch:
            return existing
        res = supabase_execute(
            "jobs.update",
            lambda: self._client.table(self._table)
            .update(patch)
            .eq("id", str(job_id))
            .execute(),
        )
        rows = res.data or []
        if not rows:
            return None
        return Job.model_validate(rows[0])

    def delete(self, job_id: UUID) -> bool:
        res = supabase_execute(
            "jobs.delete",
            lambda: self._client.table(self._table).delete().eq("id", str(job_id)).execute(),
        )
        return bool(res.data)
