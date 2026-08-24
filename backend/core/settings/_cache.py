from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import TypeVar

T = TypeVar("T")

_CACHED: list[Callable[[], object]] = []


def settings_cache(factory: Callable[[], T]) -> Callable[[], T]:
    """``lru_cache`` that registers itself so tests can reset every settings cache."""
    cached = lru_cache(maxsize=1)(factory)
    _CACHED.append(cached)
    return cached


def reset_settings_caches() -> None:
    for cached in _CACHED:
        cached.cache_clear()  # type: ignore[attr-defined]
