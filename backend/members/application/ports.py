"""Persistence and read ports for the members context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from backend.core.llm.ask import ViewerContext
from backend.core.page import PageResult
from backend.members.application.commands import (
    ClassImport,
    EntryUpsert,
    IntentsUpsert,
    MemberImport,
)
from backend.members.domain import (
    AskInterpretation,
    ClassRef,
    Member,
    MemberEntry,
    MemberIntents,
    MemberProfile,
)


@dataclass(frozen=True, slots=True)
class MemberFilters:
    q: str | None = None
    class_id: int | None = None
    class_label: str | None = None
    class_year_min: int | None = None
    class_year_max: int | None = None
    major: str | None = None
    role: str | None = None
    # any of student|ca|faculty; ``role`` stays for the single-value query parameter
    roles: tuple[str, ...] = field(default_factory=tuple)
    location: str | None = None
    # intent flags: any of cofounding|mentoring|hiring|open_to_roles|speaking|investing
    intents: tuple[str, ...] = field(default_factory=tuple)
    # "any" is what the directory's repeatable ?intent= parameter has always meant. Ask
    # asks for "all" because "open to mentoring and investing" is one person, not two.
    intents_match: str = "any"
    skills: tuple[str, ...] = field(default_factory=tuple)
    languages: tuple[str, ...] = field(default_factory=tuple)
    is_ca: bool | None = None
    has_entry: bool | None = None
    claimed_only: bool = False
    needs_review: bool | None = None
    company: str | None = None
    past_company: str | None = None
    title: str | None = None
    school: str | None = None
    degree: str | None = None
    # Group names owned by the Paths read model. Matched against member_paths as text; this
    # context never looks inside them.
    study_group: str | None = None
    first_step_group: str | None = None
    current_group: str | None = None
    # relevance (the default) | name | class
    sort: str | None = None


class MemberRepository(Protocol):
    async def search(
        self, *, skip: int, limit: int, filters: MemberFilters, viewer_member_id: UUID | None
    ) -> PageResult[Member]: ...
    async def matching_ids(self, filters: MemberFilters) -> list[UUID]: ...
    async def get_by_slug(self, slug: str) -> MemberProfile | None: ...
    async def get_by_id(self, member_id: UUID) -> MemberProfile | None: ...
    async def get_many(self, ids: list[UUID]) -> list[Member]: ...
    async def one_member_per_company(self, companies: list[str]) -> list[tuple[str, UUID, int]]: ...
    async def list_classes(self) -> list[ClassRef]: ...
    async def list_majors(self) -> list[str]: ...
    async def count(self) -> int: ...
    async def upsert_classes(self, classes: list[ClassImport]) -> int: ...
    async def upsert_member(self, payload: MemberImport) -> UUID: ...
    async def update_profile(
        self,
        member_id: UUID,
        *,
        name: str,
        first_name: str | None,
        last_name: str | None,
        headline: str | None,
        summary: str | None,
        location: str | None,
        linkedin_url: str | None,
        class_id: int,
        class_label: str,
        major: str | None,
        current_company: str | None,
        current_title: str | None,
    ) -> None: ...
    async def set_email(self, member_id: UUID, email: str | None) -> None: ...
    async def find_id_by_slug(self, slug: str) -> UUID | None: ...


class EntryRepository(Protocol):
    async def get(self, member_id: UUID) -> MemberEntry | None: ...
    async def upsert(self, member_id: UUID, payload: EntryUpsert) -> MemberEntry: ...
    async def get_intents(self, member_id: UUID) -> MemberIntents | None: ...
    async def upsert_intents(self, member_id: UUID, payload: IntentsUpsert) -> MemberIntents: ...


class ViewerGroupSource(Protocol):
    """Where the person asking is now, in the Paths read model's words.

    "others who ended up where I did" resolves against the asker's own current group. This
    context has no word for a career group: it takes the string, puts it in the viewer
    context the translator reads, and never looks inside it. The Paths implementation is
    bound in ``backend/members/api/deps.py``; nothing in this package names it.
    """

    async def current_group_of(self, member_id: UUID) -> str | None: ...


class QueryTranslator(Protocol):
    """Turns a plain-words question into a validated ``MemberQuery``.

    Two implementations exist and both are always available: one asks a language model,
    one applies keyword rules. The service picks between them, so a missing API key
    degrades the answer rather than the endpoint.
    """

    #: What the ask log records as the model behind an interpretation ("-" for rules).
    model_name: str

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> AskInterpretation: ...
