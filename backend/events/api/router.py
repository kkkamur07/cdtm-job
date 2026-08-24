from __future__ import annotations

from fastapi import APIRouter

from backend.events.api import events

router = APIRouter()
router.include_router(events.router)
