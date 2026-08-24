"""Persistence ports. Application services depend on these Protocols, never on ORM."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from backend.core.page import PageResult
from backend.jobboard.application.commands import (
    CompanyCreate,
    CompanyUpdate,
    JobCreate,
    JobUpdate,
    SeekerCreate,
    SeekerUpdate,
)
from backend.jobboard.domain import (
    Company,
    EmploymentType,
    ExperienceLevel,
    Job,
    JobAskInterpretation,
    JobStatus,
    Seeker,
    WorkArrangement,
)


@dataclass(frozen=True, slots=True)
class JobFilters:
    company_id: UUID | None = None
    status: JobStatus | None = None
    # The singular fields are the board's long-standing query parameters and stay exactly
    # as they were; the plural ones are what a translated question fills in. Both are
    # applied, so passing one of each narrows rather than replaces.
    employment_type: EmploymentType | None = None
    work_arrangement: WorkArrangement | None = None
    employment_types: tuple[EmploymentType, ...] = field(default_factory=tuple)
    work_arrangements: tuple[WorkArrangement, ...] = field(default_factory=tuple)
    experience_levels: tuple[ExperienceLevel, ...] = field(default_factory=tuple)
    posted_by_member_id: UUID | None = None
    q: str | None = None
    city: str | None = None
    country: str | None = None
    remote_only: bool | None = None
    company: str | None = None
    is_cdtm_startup: bool | None = None
    salary_min: Decimal | None = None
    posted_within_days: int | None = None
    # relevance (the default) | recent | salary
    sort: str | None = None


@dataclass(frozen=True, slots=True)
class CompanyFilters:
    industry: str | None = None
    is_cdtm_startup: bool | None = None
    hq_city: str | None = None
    q: str | None = None


class CompanyRepository(Protocol):
    async def list(
        self, *, skip: int, limit: int, filters: CompanyFilters
    ) -> PageResult[Company]: ...
    async def get(self, company_id: UUID) -> Company | None: ...
    async def get_by_slug(self, slug: str) -> Company | None: ...
    async def create(
        self, payload: CompanyCreate, *, created_by_member_id: UUID | None
    ) -> Company: ...
    async def update(self, company_id: UUID, payload: CompanyUpdate) -> Company | None: ...
    async def delete(self, company_id: UUID) -> bool: ...


class JobRepository(Protocol):
    async def list(self, *, skip: int, limit: int, filters: JobFilters) -> PageResult[Job]: ...
    async def get(self, job_id: UUID) -> Job | None: ...
    async def get_by_slug(self, slug: str) -> Job | None: ...
    async def create(self, payload: JobCreate, *, posted_by_member_id: UUID | None) -> Job: ...
    async def update(self, job_id: UUID, payload: JobUpdate) -> Job | None: ...
    async def delete(self, job_id: UUID) -> bool: ...


class SeekerRepository(Protocol):
    async def list(self, *, skip: int, limit: int) -> PageResult[Seeker]: ...
    async def get(self, seeker_id: UUID) -> Seeker | None: ...
    async def create(self, payload: SeekerCreate, *, member_id: UUID | None) -> Seeker: ...
    async def update(self, seeker_id: UUID, payload: SeekerUpdate) -> Seeker | None: ...
    async def delete(self, seeker_id: UUID) -> bool: ...


class JobQueryTranslator(Protocol):
    """Turns a plain-words question about the board into a validated ``JobQuery``."""

    #: What the ask log records as the model behind an interpretation ("-" for rules).
    model_name: str

    async def translate(
        self, question: str, *, language: str | None = None
    ) -> JobAskInterpretation: ...
