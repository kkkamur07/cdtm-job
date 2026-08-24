"""A very small in-process cache for answers that change only when the loader runs.

The directory facets, the path groups and the unfiltered Sankey are derived from tables
that no request writes: ``load_community.py`` recomputes them offline and nothing else
touches them. Recomputing them per page view costs three to seven round trips for a value
that was identical a second ago, so they are held here for a short while instead.

Dependency free on purpose. ``cachetools`` would do the same job for one cache, but nothing
in it gives the process a list of every cache it built, and that list is the whole point:
the loader and the test suite both need to empty all of them at once. Keeping a third-party
cache alongside this one only meant two expiry policies and one of them (the media
signed-URL cache) quietly outliving :func:`clear_all`, so the dependency is gone.

Thread and task safety: entries are plain dict operations with no ``await`` between the
read and the write, so a coroutine can never be suspended halfway through one. Two callers
racing on a cold key both compute the value and the second overwrites the first, which is
harmless because every cached value here is a pure read of the same rows.

Every cache registers itself, so :func:`clear_all` can drop the lot after a load. Nothing
in here is shared between processes: with more than one worker each holds its own copy and
each expires on its own, which is why the TTLs are minutes rather than hours.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

#: Every cache built in this process, so a loader run can empty all of them at once.
_CACHES: list[TTLCache] = []


class TTLCache:
    """A bounded dict whose entries expire, with least-recently-used eviction.

    ``maxsize`` is a ceiling on entries, not bytes: the values here are one facet list or
    one flow, and the key space is the handful of filter combinations a UI offers.
    """

    __slots__ = ("_entries", "_maxsize", "_ttl")

    def __init__(self, *, maxsize: int, ttl: float) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self._entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        _CACHES.append(self)

    @property
    def ttl(self) -> float:
        return self._ttl

    def get(self, key: Hashable) -> Any | None:
        """The cached value, or ``None`` when there is none or it has expired.

        ``None`` is never stored, so it is an unambiguous miss.
        """
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        # The monotonic clock, not the wall clock: a clock adjustment must not make an
        # entry immortal or expire the whole cache at once.
        if time.monotonic() >= expires_at:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return value

    def set(self, key: Hashable, value: Any) -> None:
        if value is None:
            return
        self._entries[key] = (time.monotonic() + self._ttl, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    def pop(self, key: Hashable) -> None:
        """Forget one entry, whether or not it was there.

        Expiry is not always how a cached value stops being true: a deleted image blob
        invalidates the signature over it immediately, and the entry has to go with it.
        """
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


def clear_all() -> None:
    """Drop every cached value in this process.

    Called after a career-path recompute and at the end of a community load, because those
    are the two moments the underlying rows change. Without it a reload would be invisible
    for the length of the longest TTL.
    """
    for cache in _CACHES:
        cache.clear()
