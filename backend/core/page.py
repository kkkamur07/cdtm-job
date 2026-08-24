from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageResult(Generic[T]):
    """Application-layer page (repositories return this; API maps it to ``Page[T]``)."""

    items: list[T]
    total: int
