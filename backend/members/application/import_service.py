"""Loading what ``ingest.mjs`` produced: classes, members, and Workspace e-mails.

Career paths are not computed here. They are the Paths context's read model over the same
rows, so ``scripts/platform/load_community.py`` calls this service and then asks Paths to
recompute. That keeps the loader's two steps visible in the loader instead of hidden
behind a keyword argument, and it keeps this context free of any idea of a career group.
"""

from __future__ import annotations

from uuid import UUID

from backend.members.application.commands import ClassImport, MemberImport
from backend.members.application.ports import MemberRepository


class ImportService:
    """Used by ``scripts/platform/load_community.py``: upsert what ingest.mjs produced."""

    def __init__(self, members: MemberRepository) -> None:
        self._members = members

    async def import_classes(self, classes: list[ClassImport]) -> int:
        return await self._members.upsert_classes(classes)

    async def import_member(self, payload: MemberImport) -> UUID:
        return await self._members.upsert_member(payload)

    async def bind_emails(self, email_by_slug: dict[str, str]) -> int:
        """Attach Workspace e-mails (from the directory export) to members by slug."""
        n = 0
        for slug, email in email_by_slug.items():
            member_id = await self._members.find_id_by_slug(slug)
            if member_id is None:
                continue
            await self._members.set_email(member_id, email.lower())
            n += 1
        return n
