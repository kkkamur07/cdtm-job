from __future__ import annotations

from fastapi import APIRouter

from backend.housing.api import ask, housing

#: Ask goes in first so ``/housing/ask`` is never a candidate for ``/housing/{listing_id}``.
router = APIRouter()
router.include_router(ask.router)
router.include_router(housing.router)
