"""Seeker use cases (deferred until auth + profiles exist in the database)."""

from typing import Any
from uuid import UUID


class SeekerService:
    """Placeholder application service — no `seekers` table in v1."""

    def list_seekers(self, *, limit: int = 50) -> list[dict[str, Any]]:
        del limit  # reserved for post-auth pagination
        return []

    def get_seeker(self, seeker_id: UUID) -> dict[str, Any]:
        del seeker_id
        raise ValueError("Seekers require authentication and a profiles table (post-v1).")

    def create_seeker(self) -> UUID:
        raise ValueError("Seeker registration is not implemented (post-v1).")

    def update_seeker(self, seeker_id: UUID) -> None:
        del seeker_id
        raise ValueError("Seeker updates are not implemented (post-v1).")

    def delete_seeker(self, seeker_id: UUID) -> bool:
        del seeker_id
        raise ValueError("Seeker deletion is not implemented (post-v1).")
