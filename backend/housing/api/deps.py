"""Wiring for the housing context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.core.llm import get_structured_completer
from backend.core.llm.quota import SqlQuestionMeter
from backend.housing.application.housing_ask_service import HousingAskService
from backend.housing.application.housing_service import HousingService
from backend.housing.infrastructure.housing_ask_translator_llm import LlmHousingTranslator
from backend.housing.infrastructure.housing_ask_translator_rules import RulesHousingTranslator
from backend.housing.infrastructure.housing_repository import SqlHousingRepository
from backend.identity.api.deps import DbDep


def get_housing_service(db: DbDep) -> HousingService:
    return HousingService(SqlHousingRepository(db))


def get_housing_ask_service(db: DbDep) -> HousingAskService:
    completer = get_structured_completer()
    return HousingAskService(
        SqlHousingRepository(db),
        translator=LlmHousingTranslator(completer) if completer else None,
        fallback=RulesHousingTranslator(),
        meter=SqlQuestionMeter(db),
    )


HousingServiceDep = Annotated[HousingService, Depends(get_housing_service)]
HousingAskServiceDep = Annotated[HousingAskService, Depends(get_housing_ask_service)]
