"""The little this context knows about a Member: enough to draw them on a card.

"Show me the people in this box of the Sankey" has to come back as people, not ids. This
is the shape ``SqlMemberCards`` reads out of the member tables through the metadata-free
table handles in ``infrastructure/_member_tables.py``; it is the shape of a read, not a second
model of a Member.
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
