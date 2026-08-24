from __future__ import annotations

from fastapi import APIRouter

from backend.members.api import ask, me, members

#: ``ask`` and ``me`` go in before ``members`` so ``/members/ask`` and ``/members/me`` are
#: never a candidate for ``/members/{slug}``.
router = APIRouter()
router.include_router(ask.router)
router.include_router(me.router)
router.include_router(members.router)
