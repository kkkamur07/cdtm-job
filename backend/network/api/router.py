from __future__ import annotations

from fastapi import APIRouter

from backend.network.api import network

router = APIRouter()
router.include_router(network.router)
