"""Small helpers shared by integration tests."""

from __future__ import annotations

import uuid


def integration_slug(prefix: str) -> str:
    """Unique slug fragment for parallel-safe CRUD tests."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
