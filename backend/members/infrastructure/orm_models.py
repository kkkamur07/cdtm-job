"""ORM models for the members context.

Tables: classes, members, member_classes, ca_details, positions, educations,
member_entries, member_intents.

Other contexts reference ``members.id`` by string in their own foreign keys and never
import these classes; the rows they own carry a member id and nothing else about a person.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db import Base, text_array, timestamp, uuid_pk


class ClassRow(Base):
    """A CDTM class (cohort). ``id`` is the roster id, not generated."""

    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    season: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[int | None] = mapped_column(Integer)


class MemberRow(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    roster_person_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    roster_name: Mapped[str | None] = mapped_column(Text)
    # Workspace e-mail, lowercase. Binding key for accounts.
    # Unique on lower(email): the Workspace export and the roster disagree on case, and
    # identity binds accounts with ``lower(email) = :email``, which this index also serves.
    email: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    avatar_sm_url: Mapped[str | None] = mapped_column(Text)
    avatar_lg_url: Mapped[str | None] = mapped_column(Text)
    avatar_blur: Mapped[str | None] = mapped_column(Text)
    class_label: Mapped[str | None] = mapped_column(Text)
    major: Mapped[str | None] = mapped_column(Text)
    roles: Mapped[list[str]] = text_array()
    is_ca: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    ca_alumni: Mapped[bool | None] = mapped_column(Boolean)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    match_method: Mapped[str | None] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    current_company: Mapped[str | None] = mapped_column(Text)
    current_title: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = text_array()
    languages: Mapped[list[str]] = text_array()
    company_info: Mapped[dict | None] = mapped_column(JSONB)
    # Denormalised haystack for directory search (name, headline, company, title, major,
    # class, skills, entry topics). Maintained by the loader and entry updates.
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    linkedin_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = timestamp()
    updated_at: Mapped[datetime] = timestamp()

    classes: Mapped[list[ClassRow]] = relationship(
        secondary="member_classes", lazy="selectin", order_by=ClassRow.year.desc()
    )
    positions: Mapped[list[PositionRow]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PositionRow.sort_order",
    )
    educations: Mapped[list[EducationRow]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EducationRow.sort_order",
    )
    ca_detail: Mapped[CaDetailRow | None] = relationship(
        back_populates="member", cascade="all, delete-orphan", lazy="selectin", uselist=False
    )
    entry: Mapped[MemberEntryRow | None] = relationship(
        back_populates="member", cascade="all, delete-orphan", lazy="selectin", uselist=False
    )
    intents: Mapped[MemberIntentsRow | None] = relationship(
        back_populates="member", cascade="all, delete-orphan", lazy="selectin", uselist=False
    )

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        Index("uq_members_email_lower", text("lower(email)"), unique=True),
        Index("ix_members_name", "name"),
        Index("ix_members_class_label", "class_label"),
        Index("ix_members_major", "major"),
        Index(
            "ix_members_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )


class MemberClassRow(Base):
    __tablename__ = "member_classes"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        PrimaryKeyConstraint("member_id", "class_id"),
        Index("ix_member_classes_class_id", "class_id"),
    )


class CaDetailRow(Base):
    __tablename__ = "ca_details"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    alumni: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    about: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list[str]] = text_array()
    research_fields: Mapped[list[str]] = text_array()
    email: Mapped[str | None] = mapped_column(Text)

    member: Mapped[MemberRow] = relationship(back_populates="ca_detail")


class PositionRow(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text)
    company_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    date_range: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'linkedin'"))

    member: Mapped[MemberRow] = relationship(back_populates="positions")

    __table_args__ = (Index("ix_positions_member_id", "member_id"),)


class EducationRow(Base):
    __tablename__ = "educations"

    id: Mapped[uuid.UUID] = uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    school: Mapped[str | None] = mapped_column(Text)
    degree: Mapped[str | None] = mapped_column(Text)
    date_range: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    member: Mapped[MemberRow] = relationship(back_populates="educations")

    __table_args__ = (Index("ix_educations_member_id", "member_id"),)


class MemberEntryRow(Base):
    __tablename__ = "member_entries"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    ask_me_about: Mapped[str | None] = mapped_column(Text)
    about: Mapped[str | None] = mapped_column(Text)
    current_title: Mapped[str | None] = mapped_column(Text)
    current_company: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    contact_preference: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'intro'")
    )
    contact_email: Mapped[str | None] = mapped_column(Text)
    hobbies: Mapped[list[str]] = text_array()
    topics: Mapped[list[str]] = text_array()
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'members'"))
    created_at: Mapped[datetime] = timestamp()
    updated_at: Mapped[datetime] = timestamp()

    member: Mapped[MemberRow] = relationship(back_populates="entry")

    __table_args__ = (
        CheckConstraint(
            "contact_preference in ('email','intro','linkedin')", name="contact_preference_enum"
        ),
        CheckConstraint("visibility in ('members','hidden')", name="visibility_enum"),
    )


class MemberIntentsRow(Base):
    __tablename__ = "member_intents"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    cofounding: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    mentoring: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    hiring: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    open_to_roles: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    speaking: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    investing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = timestamp()

    member: Mapped[MemberRow] = relationship(back_populates="intents")

    __table_args__ = (
        Index("ix_member_intents_cofounding", "cofounding", postgresql_where=text("cofounding")),
        Index("ix_member_intents_mentoring", "mentoring", postgresql_where=text("mentoring")),
        Index("ix_member_intents_hiring", "hiring", postgresql_where=text("hiring")),
        Index(
            "ix_member_intents_open_to_roles",
            "open_to_roles",
            postgresql_where=text("open_to_roles"),
        ),
        Index("ix_member_intents_speaking", "speaking", postgresql_where=text("speaking")),
        Index("ix_member_intents_investing", "investing", postgresql_where=text("investing")),
    )
