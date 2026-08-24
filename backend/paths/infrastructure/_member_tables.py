"""Read-only handles on the member tables this context queries.

Paths is a read model over rows the members context owns: positions, educations, classes
and stated intents. It must not import that context's ORM (ADR 0007), and it must not map
those tables a second time either, because two mapped classes for one table is how Alembic
ends up with two opinions about it.

These are lightweight ``sqlalchemy.table()`` handles instead. They carry no metadata, so
Alembic never sees them, they are exactly as much of a promise as the ``text()`` queries
``identity`` uses to read ``members.email``, and they name only the columns a path is
decided by or drawn with. If members drops one of these columns, the query breaks loudly
here rather than silently returning the wrong picture.
"""

from __future__ import annotations

from sqlalchemy import column, table

members = table(
    "members",
    column("id"),
    column("slug"),
    column("name"),
    column("headline"),
    column("avatar_sm_url"),
    column("avatar_lg_url"),
    column("avatar_blur"),
    column("location"),
    column("class_label"),
    column("major"),
    column("current_company"),
    column("current_title"),
    column("is_ca"),
)

member_classes = table("member_classes", column("member_id"), column("class_id"))

classes = table("classes", column("id"), column("year"), column("season"))

positions = table(
    "positions",
    column("member_id"),
    column("title"),
    column("company"),
    column("start_date"),
    column("is_current"),
    column("sort_order"),
)

educations = table(
    "educations",
    column("member_id"),
    column("school"),
    column("degree"),
    column("sort_order"),
)

member_intents = table(
    "member_intents",
    column("member_id"),
    column("cofounding"),
    column("mentoring"),
    column("hiring"),
    column("open_to_roles"),
    column("speaking"),
    column("investing"),
)
