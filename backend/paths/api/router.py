from __future__ import annotations

from fastapi import APIRouter

from backend.paths.api import paths

#: No prefix of its own: ``paths.router`` carries ``/paths`` and this is what
#: ``backend/core/app.py`` mounts under ``/api/v1``.
router = APIRouter()
router.include_router(paths.router)
