"""ORM models for the network context.

Tables: saved_members, intro_requests. Both hold two member ids and nothing else about
either person; the cards the API shows are read through ``member_directory.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db import Base, timestamp, uuid_pk


class SavedMemberRow(Base):
    __tablename__ = "saved_members"

    owner_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    saved_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = timestamp()

    __table_args__ = (
        PrimaryKeyConstraint("owner_member_id", "saved_member_id"),
        CheckConstraint("owner_member_id <> saved_member_id", name="not_self"),
        # The other half of the pair: the primary key covers "who did I save", nothing
        # covered the cascade that fires when the saved member is deleted.
        Index("ix_saved_members_saved_member_id", "saved_member_id"),
    )


class IntroRequestRow(Base):
    __tablename__ = "intro_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    requester_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    target_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime] = timestamp()
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status in ('pending','accepted','declined','withdrawn')", name="status_enum"
        ),
        CheckConstraint("requester_member_id <> target_member_id", name="not_self"),
        Index("ix_intro_requests_target", "target_member_id", "status"),
        Index("ix_intro_requests_requester", "requester_member_id"),
    )
