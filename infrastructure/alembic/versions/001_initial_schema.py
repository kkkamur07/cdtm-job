"""Initial schema for the merged CDTM Community platform.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-08-22

Hand-frozen from an autogenerate run against the ORM in ``infrastructure/models.py``
(``tests/integration/test_migrations.py`` keeps the two in sync). One builder per table so
the file reads like the data model; ``upgrade`` calls them in foreign-key order and
``downgrade`` reverses it.

Enumerations are TEXT columns guarded by CHECK constraints rather than Postgres ENUM types,
same as the old job board: adding a value is a one-line constraint swap instead of an
``ALTER TYPE`` that cannot run inside a transaction on older Postgres.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _create_extensions() -> None:
    # pg_trgm backs the GIN trigram index on members.search_text (ILIKE '%term%' stays fast
    # on ~1.4k rows today and on 10x that). Supabase ships the extension; local Postgres
    # needs it created once, which requires a superuser or the extension being trusted.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


# ---- community: roster and scrape snapshot ---------------------------------


def _create_classes() -> None:
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("season", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("location", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classes")),
        sa.UniqueConstraint("label", name=op.f("uq_classes_label")),
    )


def _create_members() -> None:
    op.create_table(
        "members",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("roster_person_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("roster_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("avatar_sm_url", sa.Text(), nullable=True),
        sa.Column("avatar_lg_url", sa.Text(), nullable=True),
        sa.Column("avatar_blur", sa.Text(), nullable=True),
        sa.Column("class_label", sa.Text(), nullable=True),
        sa.Column("major", sa.Text(), nullable=True),
        sa.Column(
            "roles",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("is_ca", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ca_alumni", sa.Boolean(), nullable=True),
        sa.Column("matched", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("match_method", sa.Text(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("current_company", sa.Text(), nullable=True),
        sa.Column("current_title", sa.Text(), nullable=True),
        sa.Column(
            "skills",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("company_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("search_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("linkedin_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_members_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sa.UniqueConstraint("roster_person_id", name=op.f("uq_members_roster_person_id")),
        sa.UniqueConstraint("slug", name=op.f("uq_members_slug")),
    )
    op.create_index("uq_members_email_lower", "members", [sa.text("lower(email)")], unique=True)
    op.create_index("ix_members_class_label", "members", ["class_label"], unique=False)
    op.create_index("ix_members_major", "members", ["major"], unique=False)
    op.create_index("ix_members_name", "members", ["name"], unique=False)
    op.create_index(
        "ix_members_search_text_trgm",
        "members",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )


def _create_member_classes() -> None:
    op.create_table(
        "member_classes",
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name=op.f("fk_member_classes_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_member_classes_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("member_id", "class_id", name=op.f("pk_member_classes")),
    )
    op.create_index("ix_member_classes_class_id", "member_classes", ["class_id"], unique=False)


def _create_ca_details() -> None:
    op.create_table(
        "ca_details",
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("alumni", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column(
            "responsibilities",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "research_fields",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_ca_details_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("member_id", name=op.f("pk_ca_details")),
    )


def _create_positions() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("company_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("date_range", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'linkedin'"), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_positions_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_positions")),
    )
    op.create_index("ix_positions_member_id", "positions", ["member_id"], unique=False)


def _create_educations() -> None:
    op.create_table(
        "educations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("school", sa.Text(), nullable=True),
        sa.Column("degree", sa.Text(), nullable=True),
        sa.Column("date_range", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_educations_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_educations")),
    )
    op.create_index("ix_educations_member_id", "educations", ["member_id"], unique=False)


def _create_member_paths() -> None:
    op.create_table(
        "member_paths",
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("study_group", sa.Text(), nullable=True),
        sa.Column("first_step_group", sa.Text(), nullable=True),
        sa.Column("first_step_title", sa.Text(), nullable=True),
        sa.Column("first_step_company", sa.Text(), nullable=True),
        sa.Column("current_group", sa.Text(), nullable=True),
        sa.Column("current_title", sa.Text(), nullable=True),
        sa.Column("current_company", sa.Text(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_member_paths_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("member_id", name=op.f("pk_member_paths")),
    )
    op.create_index(
        "ix_member_paths_groups",
        "member_paths",
        ["study_group", "first_step_group", "current_group"],
        unique=False,
    )


# ---- identity --------------------------------------------------------------


def _create_accounts() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("auth_user_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("member_id", sa.UUID(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_accounts_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("auth_user_id", name=op.f("uq_accounts_auth_user_id")),
        sa.UniqueConstraint("email", name=op.f("uq_accounts_email")),
        sa.UniqueConstraint("member_id", name=op.f("uq_accounts_member_id")),
    )


# ---- community: what members maintain --------------------------------------


def _create_member_entries() -> None:
    op.create_table(
        "member_entries",
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("ask_me_about", sa.Text(), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("current_title", sa.Text(), nullable=True),
        sa.Column("current_company", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column(
            "contact_preference", sa.Text(), server_default=sa.text("'intro'"), nullable=False
        ),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column(
            "hobbies",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("visibility", sa.Text(), server_default=sa.text("'members'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "contact_preference in ('email','intro','linkedin')",
            name=op.f("ck_member_entries_contact_preference_enum"),
        ),
        sa.CheckConstraint(
            "visibility in ('members','hidden')", name=op.f("ck_member_entries_visibility_enum")
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_member_entries_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("member_id", name=op.f("pk_member_entries")),
    )


def _create_member_intents() -> None:
    op.create_table(
        "member_intents",
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("cofounding", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("mentoring", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("hiring", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("open_to_roles", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("speaking", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("investing", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_member_intents_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("member_id", name=op.f("pk_member_intents")),
    )
    op.create_index(
        "ix_member_intents_cofounding",
        "member_intents",
        ["cofounding"],
        unique=False,
        postgresql_where=sa.text("cofounding"),
    )
    op.create_index(
        "ix_member_intents_hiring",
        "member_intents",
        ["hiring"],
        unique=False,
        postgresql_where=sa.text("hiring"),
    )
    op.create_index(
        "ix_member_intents_mentoring",
        "member_intents",
        ["mentoring"],
        unique=False,
        postgresql_where=sa.text("mentoring"),
    )
    op.create_index(
        "ix_member_intents_open_to_roles",
        "member_intents",
        ["open_to_roles"],
        unique=False,
        postgresql_where=sa.text("open_to_roles"),
    )
    op.create_index(
        "ix_member_intents_speaking",
        "member_intents",
        ["speaking"],
        unique=False,
        postgresql_where=sa.text("speaking"),
    )
    op.create_index(
        "ix_member_intents_investing",
        "member_intents",
        ["investing"],
        unique=False,
        postgresql_where=sa.text("investing"),
    )


def _create_saved_members() -> None:
    op.create_table(
        "saved_members",
        sa.Column("owner_member_id", sa.UUID(), nullable=False),
        sa.Column("saved_member_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "owner_member_id <> saved_member_id", name=op.f("ck_saved_members_not_self")
        ),
        sa.ForeignKeyConstraint(
            ["owner_member_id"],
            ["members.id"],
            name=op.f("fk_saved_members_owner_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["saved_member_id"],
            ["members.id"],
            name=op.f("fk_saved_members_saved_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "owner_member_id", "saved_member_id", name=op.f("pk_saved_members")
        ),
    )


def _create_intro_requests() -> None:
    op.create_table(
        "intro_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("requester_member_id", sa.UUID(), nullable=False),
        sa.Column("target_member_id", sa.UUID(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('pending','accepted','declined','withdrawn')",
            name=op.f("ck_intro_requests_status_enum"),
        ),
        sa.CheckConstraint(
            "requester_member_id <> target_member_id", name=op.f("ck_intro_requests_not_self")
        ),
        sa.ForeignKeyConstraint(
            ["requester_member_id"],
            ["members.id"],
            name=op.f("fk_intro_requests_requester_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_member_id"],
            ["members.id"],
            name=op.f("fk_intro_requests_target_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intro_requests")),
    )
    op.create_index(
        "ix_intro_requests_requester", "intro_requests", ["requester_member_id"], unique=False
    )
    op.create_index(
        "ix_intro_requests_target", "intro_requests", ["target_member_id", "status"], unique=False
    )


# ---- community: events, announcements, housing -----------------------------


def _create_events() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), server_default=sa.text("'community'"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("created_by_member_id", sa.UUID(), nullable=True),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind in ('cdtm','community','external')", name=op.f("ck_events_kind_enum")
        ),
        sa.CheckConstraint(
            "ends_at is null or ends_at >= starts_at", name=op.f("ck_events_ends_after_start")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_member_id"],
            ["members.id"],
            name=op.f("fk_events_created_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index("ix_events_starts_at", "events", ["starts_at"], unique=False)


def _create_event_rsvps() -> None:
    op.create_table(
        "event_rsvps",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('going','interested','declined')", name=op.f("ck_event_rsvps_status_enum")
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_rsvps_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_event_rsvps_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "member_id", name=op.f("pk_event_rsvps")),
    )


def _create_announcements() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_member_id", sa.UUID(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_member_id"],
            ["members.id"],
            name=op.f("fk_announcements_author_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcements")),
    )
    op.create_index(
        "ix_announcements_published_at",
        "announcements",
        [sa.literal_column("published_at DESC")],
        unique=False,
    )


def _create_announcement_reads() -> None:
    op.create_table(
        "announcement_reads",
        sa.Column("announcement_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column(
            "read_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["announcement_id"],
            ["announcements.id"],
            name=op.f("fk_announcement_reads_announcement_id_announcements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_announcement_reads_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("announcement_id", "member_id", name=op.f("pk_announcement_reads")),
    )


def _create_housing_listings() -> None:
    op.create_table(
        "housing_listings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=True),
        sa.Column("price_eur", sa.Integer(), nullable=True),
        sa.Column("rooms", sa.Numeric(precision=4, scale=1), nullable=True),
        # Nullable: "did not say" is a real answer and is not the same as "unfurnished".
        sa.Column("furnished", sa.Boolean(), nullable=True),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("available_until", sa.Date(), nullable=True),
        sa.Column(
            "photo_urls",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'"), nullable=False),
        # Shown to the owner and to admins only, so somebody deciding whether to renew can
        # see whether anybody looked.
        sa.Column("view_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind in ('offer','looking')", name=op.f("ck_housing_listings_kind_enum")
        ),
        sa.CheckConstraint(
            "status in ('open','closed')", name=op.f("ck_housing_listings_status_enum")
        ),
        sa.CheckConstraint(
            "price_eur is null or price_eur >= 0",
            name=op.f("ck_housing_listings_price_non_negative"),
        ),
        sa.CheckConstraint(
            "view_count >= 0", name=op.f("ck_housing_listings_view_count_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_housing_listings_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_housing_listings")),
    )
    op.create_index(
        "ix_housing_listings_city_status", "housing_listings", ["city", "status"], unique=False
    )
    op.create_index(
        "ix_housing_listings_member_id", "housing_listings", ["member_id"], unique=False
    )


# ---- ask (core) ------------------------------------------------------------


def _create_ask_quota() -> None:
    """How many questions one caller has asked this minute.

    The only table ``backend/core`` owns. It is operational rather than anything a board
    means: the limit protects one shared provider account, so it has to hold across every
    API instance instead of per worker. One row per caller, rewritten in place by a single
    UPSERT per question. See docs/ask.md.

    No foreign key to members on purpose: the key is a caller, and an account with no
    member entry shares the string "unbound". A meter must also keep working while the
    thing it is metering is being deleted.
    """
    op.create_table(
        "ask_quota",
        sa.Column("member_key", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asked", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("asked >= 0", name=op.f("ck_ask_quota_asked_non_negative")),
        sa.PrimaryKeyConstraint("member_key", name=op.f("pk_ask_quota")),
    )


# ---- jobboard --------------------------------------------------------------


def _create_companies() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_by_member_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("legal_name", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("careers_page_url", sa.Text(), nullable=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("full_description", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("company_size_band", sa.Text(), nullable=True),
        sa.Column("is_cdtm_startup", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("hq_city", sa.Text(), nullable=True),
        sa.Column("hq_region", sa.Text(), nullable=True),
        sa.Column("hq_country", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("twitter_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "company_size_band is null or company_size_band in ('startup','smb','mid','enterprise')",
            name=op.f("ck_companies_size_band_enum"),
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_companies_name_not_blank")),
        sa.CheckConstraint("length(trim(slug)) > 0", name=op.f("ck_companies_slug_not_blank")),
        sa.ForeignKeyConstraint(
            ["created_by_member_id"],
            ["members.id"],
            name=op.f("fk_companies_created_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint("slug", name=op.f("uq_companies_slug")),
    )


def _create_jobs() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("posted_by_member_id", sa.UUID(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("employment_type", sa.Text(), nullable=False),
        sa.Column("work_arrangement", sa.Text(), nullable=False),
        sa.Column("location_display", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("remote_eligibility_note", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("salary_period", sa.Text(), nullable=True),
        sa.Column(
            "compensation_disclosure",
            sa.Text(),
            server_default=sa.text("'undisclosed'"),
            nullable=False,
        ),
        sa.Column("experience_level", sa.Text(), nullable=False),
        sa.Column("education_level", sa.Text(), nullable=True),
        sa.Column(
            "must_have_skills",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "nice_to_have_skills",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("application_url", sa.Text(), nullable=True),
        sa.Column("application_email", sa.Text(), nullable=True),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("visa_sponsorship", sa.Boolean(), nullable=True),
        sa.Column("relocation_assistance", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "compensation_disclosure in ('public','confidential','undisclosed')",
            name=op.f("ck_jobs_compensation_disclosure_enum"),
        ),
        sa.CheckConstraint(
            "employment_type in ('full_time','part_time','contract','internship','temporary','working_student','freelance')",
            name=op.f("ck_jobs_employment_type_enum"),
        ),
        sa.CheckConstraint(
            "experience_level in ('intern','entry','mid','senior','lead')",
            name=op.f("ck_jobs_experience_level_enum"),
        ),
        sa.CheckConstraint(
            "salary_currency is null or salary_currency ~ '^[A-Za-z]{3}$'",
            name=op.f("ck_jobs_salary_currency_iso"),
        ),
        sa.CheckConstraint(
            "salary_period is null or salary_period in ('yearly','monthly','hourly')",
            name=op.f("ck_jobs_salary_period_enum"),
        ),
        sa.CheckConstraint(
            "status in ('draft','published','closed','filled')", name=op.f("ck_jobs_status_enum")
        ),
        sa.CheckConstraint(
            "work_arrangement in ('onsite','remote','hybrid')",
            name=op.f("ck_jobs_work_arrangement_enum"),
        ),
        sa.CheckConstraint(
            "length(trim(description)) > 0", name=op.f("ck_jobs_description_not_blank")
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name=op.f("ck_jobs_title_not_blank")),
        sa.CheckConstraint(
            "salary_min is null or salary_max is null or salary_min <= salary_max",
            name=op.f("ck_jobs_salary_range_ok"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_jobs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["posted_by_member_id"],
            ["members.id"],
            name=op.f("fk_jobs_posted_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("slug", name=op.f("uq_jobs_slug")),
    )
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"], unique=False)
    op.create_index("ix_jobs_posted_by_member_id", "jobs", ["posted_by_member_id"], unique=False)
    op.create_index(
        "ix_jobs_published_list",
        "jobs",
        [sa.literal_column("published_at DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'published'"),
    )


def _create_seekers() -> None:
    op.create_table(
        "seekers",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("portfolio_url", sa.Text(), nullable=True),
        sa.Column("github_url", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("resume_url", sa.Text(), nullable=True),
        sa.Column("open_to_remote", sa.Boolean(), nullable=True),
        sa.Column("preferred_work_arrangement", sa.Text(), nullable=True),
        sa.Column(
            "preferred_locations",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "desired_role_titles",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "skills",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("education_summary", sa.Text(), nullable=True),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "preferred_work_arrangement is null or preferred_work_arrangement in ('onsite','remote','hybrid')",
            name=op.f("ck_seekers_preferred_work_arrangement_enum"),
        ),
        sa.CheckConstraint(
            "length(trim(full_name)) > 0", name=op.f("ck_seekers_full_name_not_blank")
        ),
        sa.CheckConstraint(
            "years_of_experience is null or (years_of_experience >= 0 and years_of_experience <= 80)",
            name=op.f("ck_seekers_years_of_experience_range"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_seekers_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seekers")),
    )
    op.create_index("ix_seekers_member_id", "seekers", ["member_id"], unique=False)


# ---- wiring -------------------------------------------------------------

UPGRADE_ORDER = (
    _create_classes,
    _create_members,
    # companies.created_by_member_id references members, so members has to exist first.
    _create_companies,
    _create_accounts,
    _create_announcements,
    _create_ca_details,
    _create_educations,
    _create_events,
    _create_housing_listings,
    _create_intro_requests,
    _create_jobs,
    _create_member_classes,
    _create_member_entries,
    _create_member_intents,
    _create_member_paths,
    _create_positions,
    _create_saved_members,
    _create_seekers,
    _create_announcement_reads,
    _create_event_rsvps,
    _create_ask_quota,
)

DROP_ORDER = (
    "ask_quota",
    "event_rsvps",
    "announcement_reads",
    "seekers",
    "saved_members",
    "positions",
    "member_paths",
    "member_intents",
    "member_entries",
    "member_classes",
    "jobs",
    "intro_requests",
    "housing_listings",
    "events",
    "educations",
    "ca_details",
    "announcements",
    "accounts",
    # companies before members: it carries an FK to members.id.
    "companies",
    "members",
    "classes",
)


def _lock_down_data_api() -> None:
    """Keep every table out of Supabase's auto-generated REST API.

    The API talks to Postgres as the table owner (RLS does not apply to owners), but on
    Supabase the ``public`` schema is also exposed through PostgREST to the ``anon`` and
    ``authenticated`` roles, and the frontend ships the publishable key. With RLS enabled and
    no policies, those roles see zero rows; revoking the grants closes the door completely.
    Local Postgres has no such roles, hence the guard.
    """
    for table in DROP_ORDER:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon', 'authenticated')) THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated';
                EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'REVOKE ALL ON TABLES FROM anon, authenticated';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _create_extensions()
    for build in UPGRADE_ORDER:
        build()
    _lock_down_data_api()


def downgrade() -> None:
    # DROP TABLE removes the table's indexes with it, so dropping in reverse dependency
    # order is the whole story. The extension stays: other schemas may depend on it.
    for table in DROP_ORDER:
        op.drop_table(table)
