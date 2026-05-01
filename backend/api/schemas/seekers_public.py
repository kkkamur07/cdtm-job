"""Public API models for seekers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.seekers.domain.seeker import Seeker


class SeekerPublic(Seeker):
    """Response body for a single seeker profile."""

    model_config = ConfigDict(title="SeekerPublic")


class SeekersPublic(BaseModel):
    """Paginated seeker list."""

    model_config = ConfigDict(extra="forbid")

    items: list[SeekerPublic]
    total: int
