"""Wiring for the members context.

Two of these depend on the paths context, and both dependencies are here rather than any
deeper: the career group names the Ask translators offer, and where the asker works now.
Both arrive as data (strings) and neither ``application/`` nor ``domain/`` names paths.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.core.llm import get_structured_completer
from backend.core.llm.quota import SqlQuestionMeter
from backend.identity.api.deps import DbDep
from backend.members.application.ask_service import AskService
from backend.members.application.entry_service import EntryService
from backend.members.application.member_service import MemberService
from backend.members.infrastructure.ask_translator_llm import LlmQueryTranslator
from backend.members.infrastructure.ask_translator_rules import RulesQueryTranslator
from backend.members.infrastructure.entries_repository import SqlEntryRepository
from backend.members.infrastructure.members_repository import SqlMemberRepository
from backend.paths.api.deps import build_path_service
from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES


def get_member_service(db: DbDep) -> MemberService:
    return MemberService(SqlMemberRepository(db))


def get_entry_service(db: DbDep) -> EntryService:
    return EntryService(SqlEntryRepository(db), SqlMemberRepository(db))


def get_ask_service(db: DbDep) -> AskService:
    completer = get_structured_completer()
    vocabulary = {"study_groups": STUDY_GROUP_NAMES, "career_groups": CAREER_GROUP_NAMES}
    return AskService(
        SqlMemberRepository(db),
        translator=LlmQueryTranslator(completer, **vocabulary) if completer else None,
        fallback=RulesQueryTranslator(**vocabulary),
        meter=SqlQuestionMeter(db),
        viewer_groups=build_path_service(db),
    )


MemberServiceDep = Annotated[MemberService, Depends(get_member_service)]
EntryServiceDep = Annotated[EntryService, Depends(get_entry_service)]
AskServiceDep = Annotated[AskService, Depends(get_ask_service)]
