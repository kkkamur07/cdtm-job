from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemberSummary(BaseModel):
    """The little identity knows about a Member: enough to bind an Account to one.

    Community owns the Member; this is the shape ``SqlMemberDirectory`` reads out of the
    ``members`` table, not a second model of it.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    slug: str
    name: str
    email: str | None = None
    class_label: str | None = None
