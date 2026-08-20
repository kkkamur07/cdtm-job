"""Persistence ports for seekers."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.core.page import PageResult
from backend.seekers.domain.seeker import Seeker
from backend.seekers.services.commands import SeekerCreate, SeekerUpdate


class SeekerRepository(Protocol):
    def list(self, *, skip: int, limit: int) -> PageResult[Seeker]: ...

    def get(self, seeker_id: UUID) -> Seeker | None: ...

    def create(self, payload: SeekerCreate) -> Seeker: ...

    def update(self, seeker_id: UUID, payload: SeekerUpdate) -> Seeker | None: ...

    def delete(self, seeker_id: UUID) -> bool: ...
