"""ORM row -> domain mappers shared by the members repositories."""

from __future__ import annotations

from backend.members.domain import (
    Avatar,
    CaDetail,
    ClassRef,
    CompanyInfo,
    Education,
    Member,
    MemberEntry,
    MemberIntents,
    MemberProfile,
    Position,
    RosterMatch,
    Visibility,
)
from backend.members.infrastructure.orm_models import MemberRow


def _avatar(row: MemberRow) -> Avatar | None:
    if not row.avatar_sm_url or not row.avatar_lg_url:
        return None
    return Avatar(sm=row.avatar_sm_url, lg=row.avatar_lg_url, blur=row.avatar_blur)


def _intents(row: MemberRow) -> MemberIntents | None:
    return MemberIntents.model_validate(row.intents) if row.intents is not None else None


def to_member(row: MemberRow, *, is_claimed: bool = False) -> Member:
    entry = row.entry
    return Member(
        id=row.id,
        slug=row.slug,
        name=row.name,
        first_name=row.first_name,
        last_name=row.last_name,
        headline=row.headline,
        avatar=_avatar(row),
        location=(entry.location if entry and entry.location else row.location),
        linkedin_url=row.linkedin_url,
        classes=[ClassRef.model_validate(c) for c in row.classes],
        class_label=row.class_label,
        major=row.major,
        roles=list(row.roles or []),
        is_ca=row.is_ca,
        ca_alumni=row.ca_alumni,
        company=(entry.current_company if entry and entry.current_company else row.current_company),
        title=(entry.current_title if entry and entry.current_title else row.current_title),
        intents=_intents(row),
        is_claimed=is_claimed,
        updated_at=row.updated_at,
    )


def to_profile(row: MemberRow, *, is_claimed: bool = False) -> MemberProfile:
    # ``dict(model)`` hands over the field values as they are; ``model_dump()`` used to
    # serialise the Avatar, the ClassRefs and the Intents down to plain dicts so that
    # ``MemberProfile`` could build all three back out of them again. Every profile read
    # paid for that, and a MemberProfile is a Member, so the values fit as they stand.
    base = dict(to_member(row, is_claimed=is_claimed))
    return MemberProfile(
        **base,
        roster_name=row.roster_name,
        email=row.email,
        review=RosterMatch(
            matched=row.matched, match_method=row.match_method, needs_review=row.needs_review
        ),
        summary=row.summary,
        positions=[Position.model_validate(p) for p in row.positions],
        educations=[Education.model_validate(e) for e in row.educations],
        skills=list(row.skills or []),
        languages=list(row.languages or []),
        company_info=CompanyInfo.model_validate(row.company_info) if row.company_info else None,
        ca=CaDetail.model_validate(row.ca_detail) if row.ca_detail is not None else None,
        entry=MemberEntry.model_validate(row.entry) if row.entry is not None else None,
        linkedin_synced_at=row.linkedin_synced_at,
    )


def build_search_text(row: MemberRow) -> str:
    parts: list[str] = [
        row.name or "",
        row.headline or "",
        row.current_company or "",
        row.current_title or "",
        row.major or "",
        row.class_label or "",
        row.location or "",
        " ".join(row.skills or []),
    ]
    # A hidden Entry is not in the haystack. The profile correctly withholds it, but folding
    # its words into search_text made ?q=<substring> a confirmation oracle for exactly the
    # text the member asked us not to show. Both directions matter: SqlEntryRepository.upsert
    # rebuilds this string on every write, so flipping the visibility back adds it again.
    if row.entry is not None and row.entry.visibility != Visibility.HIDDEN:
        parts += [
            row.entry.ask_me_about or "",
            row.entry.current_company or "",
            row.entry.current_title or "",
            " ".join(row.entry.topics or []),
            " ".join(row.entry.hobbies or []),
        ]
    for p in row.positions or []:
        parts += [p.company or "", p.title or ""]
    # Schools and degrees are in the haystack so a free-text question ("Stanford") finds
    # people whose only Stanford connection is an education row, not just a job.
    for e in row.educations or []:
        parts += [e.school or "", e.degree or ""]
    return " ".join(x for x in parts if x).lower()
