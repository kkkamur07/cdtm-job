"""ORM models for the announcements context.

Tables: announcements, announcement_reads.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class AnnouncementRow(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="SET NULL")
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = timestamp()
    updated_at: Mapped[datetime] = timestamp()

    __table_args__ = (
        Index("ix_announcements_published_at", text("published_at DESC")),
        # The board's actual ORDER BY. ix_announcements_published_at cannot serve it: the
        # sort leads with is_pinned and falls back to created_at where published_at is null.
        Index(
            "ix_announcements_board_order",
            text("is_pinned DESC"),
            text("coalesce(published_at, created_at) DESC"),
        ),
        # Unindexed foreign key: deleting a member SET NULLs this column and scanned the
        # whole table to find the rows.
        Index("ix_announcements_author_member_id", "author_member_id"),
    )


class AnnouncementReadRow(Base):
    __tablename__ = "announcement_reads"

    announcement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    read_at: Mapped[datetime] = timestamp()

    __table_args__ = (
        PrimaryKeyConstraint("announcement_id", "member_id"),
        # The primary key leads with announcement_id, so "which of these has this member
        # read" and the unread count both had to scan. This is the column they filter on.
        Index("ix_announcement_reads_member_id", "member_id"),
    )
