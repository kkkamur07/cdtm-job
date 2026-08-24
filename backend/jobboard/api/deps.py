from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.core.llm import get_structured_completer
from backend.core.llm.quota import SqlQuestionMeter
from backend.identity.api.deps import DbDep
from backend.jobboard.application.company_service import CompanyService
from backend.jobboard.application.job_ask_service import JobAskService
from backend.jobboard.application.job_service import JobService
from backend.jobboard.application.seeker_service import SeekerService
from backend.jobboard.infrastructure.ask_translator_llm import LlmJobTranslator
from backend.jobboard.infrastructure.ask_translator_rules import RulesJobTranslator
from backend.jobboard.infrastructure.company_repository import SqlCompanyRepository
from backend.jobboard.infrastructure.job_repository import SqlJobRepository
from backend.jobboard.infrastructure.seeker_repository import SqlSeekerRepository


def get_company_service(db: DbDep) -> CompanyService:
    return CompanyService(SqlCompanyRepository(db))


def get_job_service(db: DbDep) -> JobService:
    return JobService(SqlJobRepository(db))


def get_job_ask_service(db: DbDep) -> JobAskService:
    completer = get_structured_completer()
    return JobAskService(
        SqlJobRepository(db),
        translator=LlmJobTranslator(completer) if completer else None,
        fallback=RulesJobTranslator(),
        meter=SqlQuestionMeter(db),
    )


def get_seeker_service(db: DbDep) -> SeekerService:
    return SeekerService(SqlSeekerRepository(db))


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
SeekerServiceDep = Annotated[SeekerService, Depends(get_seeker_service)]
JobAskServiceDep = Annotated[JobAskService, Depends(get_job_ask_service)]
