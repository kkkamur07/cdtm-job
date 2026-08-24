"""SQLAlchemy ORM models for the job board context (tables: companies, jobs, seekers)."""

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
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db import Base


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Who curated the record. Same shape as jobs.posted_by_member_id and
    # events.created_by_member_id: nullable, SET NULL, and never part of a request body.
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    legal_name: Mapped[str | None] = mapped_column(Text)

    logo_url: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    careers_page_url: Mapped[str | None] = mapped_column(Text)

    short_description: Mapped[str | None] = mapped_column(Text)
    full_description: Mapped[str | None] = mapped_column(Text)

    industry: Mapped[str | None] = mapped_column(Text)
    company_size_band: Mapped[str | None] = mapped_column(Text)
    is_cdtm_startup: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    hq_city: Mapped[str | None] = mapped_column(Text)
    hq_region: Mapped[str | None] = mapped_column(Text)
    hq_country: Mapped[str | None] = mapped_column(Text)

    linkedin_url: Mapped[str | None] = mapped_column(Text)
    twitter_url: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
        CheckConstraint(
            "company_size_band is null or company_size_band in "
            "('startup','smb','mid','enterprise')",
            name="size_band_enum",
        ),
    )


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    posted_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="SET NULL")
    )
    slug: Mapped[str | None] = mapped_column(Text, unique=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    employment_type: Mapped[str] = mapped_column(Text, nullable=False)
    work_arrangement: Mapped[str] = mapped_column(Text, nullable=False)

    location_display: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    remote_eligibility_note: Mapped[str | None] = mapped_column(Text)

    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(Text)
    compensation_disclosure: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'undisclosed'")
    )

    experience_level: Mapped[str] = mapped_column(Text, nullable=False)
    education_level: Mapped[str | None] = mapped_column(Text)
    must_have_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    nice_to_have_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    image_url: Mapped[str | None] = mapped_column(Text)
    application_url: Mapped[str | None] = mapped_column(Text)
    application_email: Mapped[str | None] = mapped_column(Text)
    valid_through: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    visa_sponsorship: Mapped[bool | None] = mapped_column(Boolean)
    relocation_assistance: Mapped[bool | None] = mapped_column(Boolean)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("length(trim(description)) > 0", name="description_not_blank"),
        CheckConstraint(
            "employment_type in ('full_time','part_time','contract','internship',"
            "'temporary','working_student','freelance')",
            name="employment_type_enum",
        ),
        CheckConstraint(
            "work_arrangement in ('onsite','remote','hybrid')", name="work_arrangement_enum"
        ),
        CheckConstraint(
            "salary_currency is null or salary_currency ~ '^[A-Za-z]{3}$'",
            name="salary_currency_iso",
        ),
        CheckConstraint(
            "salary_period is null or salary_period in ('yearly','monthly','hourly')",
            name="salary_period_enum",
        ),
        CheckConstraint(
            "compensation_disclosure in ('public','confidential','undisclosed')",
            name="compensation_disclosure_enum",
        ),
        CheckConstraint(
            "experience_level in ('intern','entry','mid','senior','lead')",
            name="experience_level_enum",
        ),
        CheckConstraint("status in ('draft','published','closed','filled')", name="status_enum"),
        CheckConstraint(
            "salary_min is null or salary_max is null or salary_min <= salary_max",
            name="salary_range_ok",
        ),
        Index("ix_jobs_company_id", "company_id"),
        Index("ix_jobs_posted_by_member_id", "posted_by_member_id"),
        Index(
            "ix_jobs_published_list",
            text("published_at DESC"),
            postgresql_where=text("status = 'published'"),
        ),
    )


class SeekerRow(Base):
    __tablename__ = "seekers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)

    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    portfolio_url: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(Text)

    headline: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    resume_url: Mapped[str | None] = mapped_column(Text)

    open_to_remote: Mapped[bool | None] = mapped_column(Boolean)
    preferred_work_arrangement: Mapped[str | None] = mapped_column(Text)
    preferred_locations: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    desired_role_titles: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    years_of_experience: Mapped[int | None] = mapped_column(Integer)
    education_summary: Mapped[str | None] = mapped_column(Text)
    available_from: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint(
            "preferred_work_arrangement is null or preferred_work_arrangement in "
            "('onsite','remote','hybrid')",
            name="preferred_work_arrangement_enum",
        ),
        CheckConstraint(
            "years_of_experience is null or "
            "(years_of_experience >= 0 and years_of_experience <= 80)",
            name="years_of_experience_range",
        ),
        Index("ix_seekers_member_id", "member_id"),
    )
