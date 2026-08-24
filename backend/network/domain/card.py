"""The little this context knows about a Member: enough to draw them on a card.

Members owns the person. What a saved-people list or an intro request has to show is a
face, a name and a line about what they do, and that is all ``SqlMemberDirectory`` reads
out of the member tables. It is the shape of a read, not a second model of a Member: the
same idea as ``backend/identity/domain/directory.py``.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemberCard(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    slug: str
    name: str
    headline: str | None = None
    avatar_sm_url: str | None = None
    avatar_lg_url: str | None = None
    avatar_blur: str | None = None
    location: str | None = None
    class_label: str | None = None
    major: str | None = None
    company: str | None = None
    title: str | None = None
    is_ca: bool = False
