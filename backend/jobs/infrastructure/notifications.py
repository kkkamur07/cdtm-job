"""Persistence for outbound notification attempts (idempotency + audit)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client


class NotificationLogRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def try_claim(
        self,
        *,
        channel: str,
        idempotency_key: str,
        job_id: UUID | None,
        payload: dict[str, Any],
    ) -> bool:
        """Insert a pending row. Returns False if ``idempotency_key`` already exists."""
        row = {
            "channel": channel,
            "idempotency_key": idempotency_key,
            "job_id": str(job_id) if job_id else None,
            "payload": payload,
            "status": "pending",
        }
        try:
            res = self._client.table("notifications_log").insert(row).execute()
        except APIError as e:
            msg = str(e).lower()
            if "duplicate" in msg or "unique" in msg or "23505" in msg:
                return False
            raise ValueError(f"notifications_log insert failed: {e!s}") from e
        return bool(res.data)

    def mark(self, idempotency_key: str, status: str, error: str | None = None) -> None:
        patch: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if error is not None:
            patch["error"] = error
        self._client.table("notifications_log").update(patch).eq("idempotency_key", idempotency_key).execute()
