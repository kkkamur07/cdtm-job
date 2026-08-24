from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(include_in_schema=False)


@router.get("/")
async def root() -> dict[str, str]:
    return {"service": "cdtm-community-api", "docs": "/docs", "health": "/health"}
