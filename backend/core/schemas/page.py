from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Offset page, same shape the original job board exposed: ``{items, total}``."""

    items: list[T]
    total: int
