"""ORM model for the paths context (table: member_paths).

A read model. Every column is derived from a member's positions, educations and class by
``paths_classifier.py``; nothing here is edited by a person, and losing the table costs a
recompute rather than data. There is no relationship to ``MemberRow``: paths reads the member
tables through the metadata-free table handles in ``_member_tables.py`` and never imports the
members context.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db import Base, timestamp


class MemberPathRow(Base):
    __tablename__ = "member_paths"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    study_group: Mapped[str | None] = mapped_column(Text)
    first_step_group: Mapped[str | None] = mapped_column(Text)
    first_step_title: Mapped[str | None] = mapped_column(Text)
    first_step_company: Mapped[str | None] = mapped_column(Text)
    current_group: Mapped[str | None] = mapped_column(Text)
    current_title: Mapped[str | None] = mapped_column(Text)
    current_company: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = timestamp()

    __table_args__ = (
        Index("ix_member_paths_groups", "study_group", "first_step_group", "current_group"),
    )
