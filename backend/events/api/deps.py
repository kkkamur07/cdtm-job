"""Wiring for the events context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.events.application.event_service import EventService
from backend.events.infrastructure.events_repository import SqlEventRepository
from backend.identity.api.deps import DbDep


def get_event_service(db: DbDep) -> EventService:
    return EventService(SqlEventRepository(db))


EventServiceDep = Annotated[EventService, Depends(get_event_service)]
