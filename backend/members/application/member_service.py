"""Members: reading the directory and one member's profile, and who may see what."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.core.page import PageResult
from backend.members.application.commands import (
    MemberImport,
    SelfProfileCreate,
    SelfProfileUpdate,
)
from backend.members.application.ports import (
    MemberFilters,
    MemberRepository,
)
from backend.members.domain import (
    ClassRef,
    CompanyContact,
    MatchMethod,
    Member,
    MemberProfile,
    Role,
    Visibility,
)


def _slugify(name: str) -> str:
    """A URL slug from a display name, matching the shape ``ingest.mjs`` writes.

    ASCII-fold, lower-case, keep letters and digits, collapse the rest to single hyphens.
    Emoji and punctuation a member puts in their name (they do) drop out rather than
    landing in a URL. Empty after folding falls back to ``member`` so a slug always exists.
    """
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug or "member"


class MemberService:
    def __init__(self, members: MemberRepository) -> None:
        self._members = members

    async def count(self) -> int:
        return await self._members.count()

    async def search(
        self, *, skip: int, limit: int, filters: MemberFilters, actor: Actor | None
    ) -> PageResult[Member]:
        # Which members the loader flagged is the same admin-only fact as the ``review``
        # block on a profile. Leaving it filterable would hand it to anybody who asked for
        # a list instead of a card.
        if filters.needs_review is not None and not (actor and actor.is_admin):
            raise ForbiddenError("needs_review is an admin filter")
        return await self._members.search(
            skip=skip,
            limit=limit,
            filters=filters,
            viewer_member_id=actor.member_id if actor else None,
        )

    async def get_profile(self, slug: str, actor: Actor | None) -> MemberProfile:
        profile = await self._members.get_by_slug(slug)
        if profile is None:
            raise NotFoundError(f"member {slug!r} not found")
        return self._redact(profile, actor)

    async def get_profile_by_id(self, member_id: UUID, actor: Actor | None) -> MemberProfile:
        profile = await self._members.get_by_id(member_id)
        if profile is None:
            raise NotFoundError("member not found")
        return self._redact(profile, actor)

    async def create_self_profile(
        self, command: SelfProfileCreate, *, email: str, avatar_url: str | None
    ) -> UUID:
        """Create the member row a signed-in account is claiming for itself.

        The e-mail and avatar are the account's own (from Google), not fields on the form:
        that is what makes this a claim of *yourself*. The class label is resolved from the
        chosen id so the card text and the class filter never disagree. The write reuses the
        loader's upsert path, with the roster-match bookkeeping set to a deliberate
        ``override`` (a human claimed this, no scrape guessed it) and no review flag.
        """
        classes = {c.id: c for c in await self._members.list_classes()}
        chosen = classes.get(command.class_id)
        if chosen is None:
            raise NotFoundError(f"class {command.class_id} not found")

        slug = await self._unique_slug(_slugify(command.name))
        first, _, last = command.name.strip().partition(" ")
        payload = MemberImport(
            slug=slug,
            name=command.name.strip(),
            first_name=first or None,
            last_name=last or None,
            email=email,
            headline=command.headline,
            summary=command.summary,
            location=command.location,
            linkedin_url=command.linkedin_url,
            avatar_sm_url=avatar_url,
            avatar_lg_url=avatar_url,
            class_ids=[chosen.id],
            class_label=chosen.label,
            major=command.major,
            roles=[Role.STUDENT],
            matched=True,
            match_method=MatchMethod.OVERRIDE,
            needs_review=False,
            current_company=command.current_company,
            current_title=command.current_title,
        )
        return await self._members.upsert_member(payload)

    async def update_self_profile(self, member_id: UUID, command: SelfProfileUpdate) -> None:
        """Update the profile fields a member maintains by hand, leaving the rest alone.

        Only the scalar profile fields and the class membership are written. The scrape's
        positions, educations and skills, the account's e-mail and avatar, and the slug are
        deliberately untouched: an edit is not a re-import. The chosen class is resolved to
        its label here for the same reason it is on create, so the card and the class filter
        never disagree.
        """
        classes = {c.id: c for c in await self._members.list_classes()}
        chosen = classes.get(command.class_id)
        if chosen is None:
            raise NotFoundError(f"class {command.class_id} not found")

        first, _, last = command.name.strip().partition(" ")
        await self._members.update_profile(
            member_id,
            name=command.name.strip(),
            first_name=first or None,
            last_name=last or None,
            headline=command.headline,
            summary=command.summary,
            location=command.location,
            linkedin_url=command.linkedin_url,
            class_id=chosen.id,
            class_label=chosen.label,
            major=command.major,
            current_company=command.current_company,
            current_title=command.current_title,
        )

    async def _unique_slug(self, base: str) -> str:
        """`base`, or `base-2`, `base-3`, ... : the first that no member holds.

        Two people with the same name is normal here; the slug is what tells their URLs
        apart, so it cannot collide with a row the scrape already wrote.
        """
        if await self._members.find_id_by_slug(base) is None:
            return base
        n = 2
        while await self._members.find_id_by_slug(f"{base}-{n}") is not None:
            n += 1
        return f"{base}-{n}"

    @staticmethod
    def _redact(profile: MemberProfile, actor: Actor | None) -> MemberProfile:
        is_self = actor is not None and actor.member_id == profile.id
        is_admin = actor is not None and actor.is_admin
        if (
            profile.entry
            and profile.entry.visibility == Visibility.HIDDEN
            and not (is_self or is_admin)
        ):
            profile = profile.model_copy(update={"entry": None})
        if not (is_self or is_admin):
            # A Center Assistant's address is a second e-mail on the same person, on a
            # nested model. Nulling only ``email`` left ``ca.email`` going out to every
            # signed-in Member, which is the whole redaction defeated by one indirection.
            update: dict = {"email": None}
            if profile.ca is not None:
                update["ca"] = profile.ca.model_copy(update={"email": None})
            profile = profile.model_copy(update=update)
        # Roster-matching bookkeeping is for the admin bind page only. Not even the member
        # it describes sees how the loader decided the tile was theirs.
        if not is_admin:
            profile = profile.model_copy(update={"review": None})
        return profile

    async def lookup(self, ids: list[UUID]) -> list[Member]:
        """Cards for the authors behind jobs, listings, events and announcements.

        Duplicates collapse and the first 50 ids win: the caller is a page, not an export.
        """
        unique = list(dict.fromkeys(ids))[:50]
        return await self._members.get_many(unique)

    async def contacts_at(self, companies: list[str]) -> list[CompanyContact]:
        """One member per company name, for a page that lists many companies at once.

        Same rules as ``lookup``: duplicates collapse, the first 50 names win, and a name
        nobody matches is simply absent from the answer rather than an error. Blank names
        are dropped before they reach the database.
        """
        unique = list(dict.fromkeys(c.strip() for c in companies if c.strip()))[:50]
        hits = await self._members.one_member_per_company(unique)
        cards = {
            m.id: m for m in await self._members.get_many([member_id for _, member_id, _ in hits])
        }
        by_name = {
            name: CompanyContact(company=name, member=cards[member_id], total=total)
            for name, member_id, total in hits
            if member_id in cards
        }
        # Answer in the order asked for, so the caller can zip it against its own rows.
        return [by_name[name] for name in unique if name in by_name]

    async def list_classes(self) -> list[ClassRef]:
        return await self._members.list_classes()

    async def list_majors(self) -> list[str]:
        return await self._members.list_majors()
