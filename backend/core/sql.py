"""SQL fragments every context's repositories need and none of them owns."""

from __future__ import annotations


def ilike_contains(term: str) -> str:
    """ILIKE pattern for "contains term", with the user's % and _ treated as literal text."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
