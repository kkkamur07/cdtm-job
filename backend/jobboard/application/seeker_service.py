"""Application service: use-case orchestration for seeker."""

from __future__ import annotations

from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult
from backend.jobboard.application.commands import (
    SeekerCreate,
    SeekerUpdate,
)
from backend.jobboard.application.ports import (
    SeekerRepository,
)
from backend.jobboard.application.visibility import can_manage_seeker, seeker_for_viewer
from backend.jobboard.domain import Seeker


class SeekerService:
    def __init__(self, repo: SeekerRepository) -> None:
        self._repo = repo

    async def list_seekers(
        self, *, skip: int = 0, limit: int = 50, actor: Actor | None = None
    ) -> PageResult[Seeker]:
        result = await self._repo.list(skip=skip, limit=limit)
        return PageResult(
            items=[seeker_for_viewer(s, actor) for s in result.items], total=result.total
        )

    async def get_seeker(self, seeker_id: UUID, actor: Actor | None = None) -> Seeker:
        row = await self._repo.get(seeker_id)
        if row is None:
            raise NotFoundError(f"Seeker {seeker_id} not found")
        return seeker_for_viewer(row, actor)

    async def create_seeker(self, payload: SeekerCreate, *, member_id: UUID | None) -> Seeker:
        """The profile belongs to whoever is signed in. Callers cannot name someone else."""
        return await self._repo.create(payload, member_id=member_id)

    async def update_seeker(self, actor: Actor, seeker_id: UUID, payload: SeekerUpdate) -> Seeker:
        await self._owned(actor, seeker_id, "edit")
        row = await self._repo.update(seeker_id, payload)
        if row is None:
            raise NotFoundError(f"Seeker {seeker_id} not found")
        return row

    async def delete_seeker(self, actor: Actor, seeker_id: UUID) -> None:
        await self._owned(actor, seeker_id, "delete")
        if not await self._repo.delete(seeker_id):
            raise NotFoundError(f"Seeker {seeker_id} not found")

    async def _owned(self, actor: Actor, seeker_id: UUID, what: str) -> Seeker:
        row = await self._repo.get(seeker_id)
        if row is None:
            raise NotFoundError(f"Seeker {seeker_id} not found")
        if not can_manage_seeker(row, actor):
            raise ForbiddenError(f"only the seeker or an admin can {what} this profile")
        return row
