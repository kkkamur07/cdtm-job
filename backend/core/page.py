"""Shared pagination result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageResult(Generic[T]):
    items: list[T]
    total: int
