from __future__ import annotations

from fastapi import APIRouter

from backend.announcements.api import announcements

router = APIRouter()
router.include_router(announcements.router)
