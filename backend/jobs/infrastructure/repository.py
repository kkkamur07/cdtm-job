"""Supabase / PostgREST adapters for jobs (infrastructure).

Robustness notes:
- PostgREST has no multi-statement transaction in the Python client for insert+children; on
  failure after the parent insert we **compensate** by deleting the orphan job row.
- Updates that replace locations **delete then insert**; if insert fails, the job is left
  without locations — treat as bug; for stronger guarantees add a Postgres RPC that wraps
  both in one transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

from jobs.application.commands import CreateJobCommand, UpdateJobCommand


def _decimal_or_none(v: Decimal | None) -> float | None:
    if v is None:
        return None
    return float(v)


class SupabaseJobRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def _delete_job_row(self, job_id: UUID) -> None:
        try:
            self._client.table("jobs").delete().eq("id", str(job_id)).execute()
        except APIError:
            # Best-effort cleanup; caller already handles primary error path
            pass

    def insert_job_with_locations(self, command: CreateJobCommand) -> UUID:
        job_row: dict[str, Any] = {
            "company_id": str(command.company_id),
            "title": command.title,
            "slug": command.slug,
            "description": command.description,
            "summary": command.summary,
            "workplace_type": command.workplace_type,
            "employment_type": command.employment_type,
            "experience_level": command.experience_level,
            "department": command.department,
            "salary_min": _decimal_or_none(command.salary_min),
            "salary_max": _decimal_or_none(command.salary_max),
            "salary_currency": command.salary_currency.upper(),
            "application_url": command.application_url,
            "application_email": command.application_email,
            "visa_sponsorship": command.visa_sponsorship,
            "status": command.status,
        }
        if command.status == "published":
            job_row["published_at"] = datetime.now(UTC).isoformat()

        job_id: UUID | None = None
        try:
            job_res = self._client.table("jobs").insert(job_row).execute()
        except APIError as e:
            raise ValueError(self._format_api_error("insert job", e)) from e
        if not job_res.data:
            raise ValueError("Failed to insert job (no data returned)")

        job_id = UUID(job_res.data[0]["id"])

        loc_rows = [
            {
                "job_id": str(job_id),
                "label": loc.label,
                "is_primary": loc.is_primary,
                "country_code": loc.country_code,
                "city": loc.city,
                "sort_order": loc.sort_order,
            }
            for loc in command.locations
        ]
        try:
            loc_res = self._client.table("job_locations").insert(loc_rows).execute()
        except APIError as e:
            self._delete_job_row(job_id)
            raise ValueError(self._format_api_error("insert job_locations", e)) from e
        if not loc_res.data:
            self._delete_job_row(job_id)
            raise ValueError("Failed to insert job locations (no data returned)")

        return job_id

    def get_job_by_id(self, job_id: UUID) -> dict[str, Any] | None:
        try:
            res = self._client.table("jobs").select("*").eq("id", str(job_id)).limit(1).execute()
        except APIError as e:
            raise ValueError(self._format_api_error("select job", e)) from e
        if not res.data:
            return None
        return res.data[0]

    def list_published_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        try:
            res = (
                self._client.table("jobs")
                .select("*")
                .eq("status", "published")
                .order("published_at", desc=True)
                .limit(limit)
                .execute()
            )
        except APIError as e:
            raise ValueError(self._format_api_error("list published jobs", e)) from e
        return list(res.data or [])

    def delete_job(self, job_id: UUID) -> bool:
        """Return True if a row was deleted."""
        try:
            res = self._client.table("jobs").delete().eq("id", str(job_id)).execute()
        except APIError as e:
            raise ValueError(self._format_api_error("delete job", e)) from e
        return bool(res.data)

    def update_job(self, job_id: UUID, command: UpdateJobCommand) -> None:
        existing = self.get_job_by_id(job_id)
        if existing is None:
            raise ValueError("Job not found")

        patch = command.model_dump(exclude_unset=True)
        locations = patch.pop("locations", None)

        update_row: dict[str, Any] = {}
        field_map = {
            "title",
            "slug",
            "description",
            "summary",
            "workplace_type",
            "employment_type",
            "experience_level",
            "department",
            "salary_min",
            "salary_max",
            "salary_currency",
            "application_url",
            "application_email",
            "visa_sponsorship",
            "status",
        }
        for key in field_map:
            if key not in patch:
                continue
            val = patch[key]
            if key in {"salary_min", "salary_max"}:
                update_row[key] = _decimal_or_none(val)  # type: ignore[arg-type]
            elif key == "salary_currency" and val is not None:
                update_row[key] = str(val).upper()
            else:
                update_row[key] = val

        new_status = update_row.get("status", existing.get("status"))
        old_status = existing.get("status")
        if new_status == "published" and old_status != "published":
            update_row["published_at"] = datetime.now(UTC).isoformat()

        if locations is not None and not update_row:
            update_row["updated_at"] = datetime.now(UTC).isoformat()
        elif update_row:
            update_row["updated_at"] = datetime.now(UTC).isoformat()

        if update_row:
            try:
                self._client.table("jobs").update(update_row).eq("id", str(job_id)).execute()
            except APIError as e:
                raise ValueError(self._format_api_error("update job", e)) from e

        if locations is not None:
            loc_res = None
            try:
                self._client.table("job_locations").delete().eq("job_id", str(job_id)).execute()
                loc_rows = [
                    {
                        "job_id": str(job_id),
                        "label": loc.label,
                        "is_primary": loc.is_primary,
                        "country_code": loc.country_code,
                        "city": loc.city,
                        "sort_order": loc.sort_order,
                    }
                    for loc in (command.locations or [])
                ]
                loc_res = self._client.table("job_locations").insert(loc_rows).execute()
            except APIError as e:
                raise ValueError(self._format_api_error("replace job_locations", e)) from e
            if loc_res is None or not loc_res.data:
                raise ValueError("Failed to replace job locations (no data returned)")

    @staticmethod
    def _format_api_error(action: str, err: APIError) -> str:
        return f"{action} failed: {err!s}"
