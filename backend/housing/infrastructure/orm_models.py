"""ORM model for the housing context (table: housing_listings)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db import Base, text_array, timestamp, uuid_pk


class HousingListingRow(Base):
    __tablename__ = "housing_listings"

    id: Mapped[uuid.UUID] = uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str | None] = mapped_column(Text)
    price_eur: Mapped[int | None] = mapped_column(Integer)
    rooms: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    # Nullable on purpose: an owner who did not say is "unknown", not "unfurnished". The
    # filter falls back to matching the words in the title and description for those rows.
    furnished: Mapped[bool | None] = mapped_column(Boolean)
    available_from: Mapped[date | None] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    photo_urls: Mapped[list[str]] = text_array()
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    # How many other members have opened the listing. Only the owner and an admin are shown
    # the number; it exists so somebody deciding whether to renew can see whether anyone
    # looked.
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Listings go stale quietly; a renew action moves this forward, the board hides it after.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = timestamp()
    updated_at: Mapped[datetime] = timestamp()

    __table_args__ = (
        CheckConstraint("kind in ('offer','looking')", name="kind_enum"),
        CheckConstraint("status in ('open','closed')", name="status_enum"),
        CheckConstraint("price_eur is null or price_eur >= 0", name="price_non_negative"),
        CheckConstraint("view_count >= 0", name="view_count_non_negative"),
        Index("ix_housing_listings_city_status", "city", "status"),
        Index("ix_housing_listings_member_id", "member_id"),
        # The board's default order.
        Index("ix_housing_listings_created_at", text("created_at DESC")),
    )
