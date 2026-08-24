"""Public response models for the events API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.events.domain import Event


class EventPublic(Event):
    model_config = ConfigDict(title="EventPublic")


class EventsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EventPublic]
    total: int
