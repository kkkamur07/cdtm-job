"""Seeker application service — CRUD orchestration."""

from __future__ import annotations

from uuid import UUID

from backend.core.errors import NotFoundError
from backend.core.page import PageResult
from backend.seekers.domain.seeker import Seeker
from backend.seekers.services.commands import SeekerCreate, SeekerUpdate
from backend.seekers.services.ports import SeekerRepository


class SeekerService:
    def __init__(self, repo: SeekerRepository) -> None:
        self._repo = repo

    def list_seekers(self, *, skip: int = 0, limit: int = 50) -> PageResult[Seeker]:
        skip = max(skip, 0)
        limit = min(max(limit, 1), 100)
        return self._repo.list(skip=skip, limit=limit)

    def get_seeker(self, seeker_id: UUID) -> Seeker:
        row = self._repo.get(seeker_id)
        if row is None:
            raise NotFoundError(f"Seeker {seeker_id} not found")
        return row

    def create_seeker(self, payload: SeekerCreate) -> Seeker:
        return self._repo.create(payload)

    def update_seeker(self, seeker_id: UUID, payload: SeekerUpdate) -> Seeker:
        row = self._repo.update(seeker_id, payload)
        if row is None:
            raise NotFoundError(f"Seeker {seeker_id} not found")
        return row

    def delete_seeker(self, seeker_id: UUID) -> None:
        if not self._repo.delete(seeker_id):
            raise NotFoundError(f"Seeker {seeker_id} not found")
