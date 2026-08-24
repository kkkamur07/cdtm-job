"""Wiring for the paths context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.identity.api.deps import DbDep
from backend.paths.application.path_service import PathService
from backend.paths.infrastructure.career_history import SqlCareerHistorySource
from backend.paths.infrastructure.member_cards import SqlMemberCards
from backend.paths.infrastructure.paths_classifier import compute_member_path
from backend.paths.infrastructure.paths_repository import SqlPathRepository


def build_path_service(db: DbDep) -> PathService:
    return PathService(
        SqlPathRepository(db),
        SqlMemberCards(db),
        SqlCareerHistorySource(db),
        compute_member_path,
    )


PathServiceDep = Annotated[PathService, Depends(build_path_service)]
