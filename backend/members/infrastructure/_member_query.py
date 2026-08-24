"""The WHERE clause behind ``MemberFilters``.

It lives on its own because the directory endpoint, the Ask endpoint and the member id set
the Paths flow is drawn over all build the same predicates, and spelling a dozen of them
out twice is how two filters quietly start meaning different things.
"""

from __future__ import annotations

from sqlalchemy import Select, and_, exists, func, or_, select, text

from backend.core.sql import ilike_contains
from backend.members.application.ports import MemberFilters
from backend.members.infrastructure.orm_models import (
    ClassRow,
    EducationRow,
    MemberClassRow,
    MemberEntryRow,
    MemberIntentsRow,
    MemberRow,
    PositionRow,
)

INTENT_COLUMNS = {
    "cofounding": MemberIntentsRow.cofounding,
    "mentoring": MemberIntentsRow.mentoring,
    "hiring": MemberIntentsRow.hiring,
    "open_to_roles": MemberIntentsRow.open_to_roles,
    "speaking": MemberIntentsRow.speaking,
    "investing": MemberIntentsRow.investing,
}

#: Path group columns, matched as text. ``member_paths`` belongs to the paths context, so
#: it is read the way identity reads ``members.email``: a correlated EXISTS in raw SQL,
#: not an imported ORM class. The column name is chosen here from a fixed set, never from
#: anything a caller typed.
_PATH_GROUP_COLUMNS = {
    "study_group": "study_group",
    "first_step_group": "first_step_group",
    "current_group": "current_group",
}


def claimed_subquery():
    # accounts table lives in the identity context; read-only correlated exists.
    return text("exists (select 1 from accounts a where a.member_id = members.id)")


def _ci_array_overlap(column, values: list[str]):
    """`column` (a ``text[]``) shares at least one element with `values`, case-insensitively.

    Postgres array overlap (``&&``) matches elements exactly, so a translator that emits
    ``machine learning`` never finds the stored ``Machine Learning`` and the answer is a
    silent zero. Unnest the array, lower each element, and test membership against the
    lowered filter values instead. Blank values are dropped so an empty term cannot widen
    the match to everyone.
    """
    lowered = [v.lower() for v in (s.strip() for s in values) if v.strip()]
    if not lowered:
        return None
    # ``unnest`` is a single-column set-returning function, so it reads as a column value
    # (its own lateral FROM), not a table with a named column.
    element = func.unnest(column).column_valued("value")
    return select(1).where(func.lower(element).in_(lowered)).exists()


def _path_group_exists(field: str, value: str):
    column = _PATH_GROUP_COLUMNS[field]
    return text(
        f"exists (select 1 from member_paths p "  # noqa: S608
        f"where p.member_id = members.id and p.{column} = :{field})"
    ).bindparams(**{field: value})


def apply_member_filters(stmt: Select, f: MemberFilters) -> Select:
    """Add every predicate ``f`` asks for to ``stmt``, which must already select members.

    The education and position predicates are correlated EXISTS over ILIKE. No index is
    added for them: the directory is about three thousand members with a handful of rows
    each, so the planner's sequential scan finishes in single-digit milliseconds, and a
    trigram index on a column nobody sorts by would be maintenance for nothing.
    """
    if f.q:
        q = f.q.strip().lower()
        stmt = stmt.where(MemberRow.search_text.ilike(ilike_contains(q)))
    if f.class_id is not None:
        stmt = stmt.where(
            exists().where(
                and_(
                    MemberClassRow.member_id == MemberRow.id,
                    MemberClassRow.class_id == f.class_id,
                )
            )
        )
    if f.class_label:
        stmt = stmt.where(MemberRow.class_label == f.class_label)
    if f.class_year_min is not None or f.class_year_max is not None:
        year = select(ClassRow.id).where(
            ClassRow.id == MemberClassRow.class_id,
            MemberClassRow.member_id == MemberRow.id,
        )
        if f.class_year_min is not None:
            year = year.where(ClassRow.year >= f.class_year_min)
        if f.class_year_max is not None:
            year = year.where(ClassRow.year <= f.class_year_max)
        stmt = stmt.where(year.exists())
    if f.major:
        # Exact: majors come from the roster and the directory offers them as a facet, so
        # a substring match would silently fold "Business" into "Business Administration".
        stmt = stmt.where(MemberRow.major == f.major)
    if f.role:
        stmt = stmt.where(MemberRow.roles.any(f.role))
    if f.roles:
        stmt = stmt.where(MemberRow.roles.overlap(list(f.roles)))
    if f.location:
        stmt = stmt.where(MemberRow.location.ilike(ilike_contains(f.location)))
    if f.company:
        stmt = stmt.where(
            or_(
                MemberRow.current_company.ilike(ilike_contains(f.company)),
                MemberRow.search_text.ilike(ilike_contains(f.company.lower())),
            )
        )
    if f.past_company:
        stmt = stmt.where(
            exists().where(
                and_(
                    PositionRow.member_id == MemberRow.id,
                    PositionRow.company.ilike(ilike_contains(f.past_company)),
                )
            )
        )
    if f.title:
        stmt = stmt.where(
            or_(
                MemberRow.current_title.ilike(ilike_contains(f.title)),
                exists().where(
                    and_(
                        PositionRow.member_id == MemberRow.id,
                        PositionRow.title.ilike(ilike_contains(f.title)),
                    )
                ),
            )
        )
    if f.school:
        stmt = stmt.where(
            exists().where(
                and_(
                    EducationRow.member_id == MemberRow.id,
                    EducationRow.school.ilike(ilike_contains(f.school)),
                )
            )
        )
    if f.degree:
        stmt = stmt.where(
            exists().where(
                and_(
                    EducationRow.member_id == MemberRow.id,
                    EducationRow.degree.ilike(ilike_contains(f.degree)),
                )
            )
        )
    if f.study_group:
        stmt = stmt.where(_path_group_exists("study_group", f.study_group))
    if f.first_step_group:
        stmt = stmt.where(_path_group_exists("first_step_group", f.first_step_group))
    if f.current_group:
        stmt = stmt.where(_path_group_exists("current_group", f.current_group))
    if f.is_ca is not None:
        stmt = stmt.where(MemberRow.is_ca.is_(f.is_ca))
    if f.needs_review is not None:
        stmt = stmt.where(MemberRow.needs_review.is_(f.needs_review))
    if f.skills:
        clause = _ci_array_overlap(MemberRow.skills, list(f.skills))
        if clause is not None:
            stmt = stmt.where(clause)
    if f.languages:
        clause = _ci_array_overlap(MemberRow.languages, list(f.languages))
        if clause is not None:
            stmt = stmt.where(clause)
    if f.intents:
        cols = [INTENT_COLUMNS[i] for i in f.intents if i in INTENT_COLUMNS]
        if cols:
            combine = and_ if f.intents_match == "all" else or_
            stmt = stmt.where(
                exists().where(
                    and_(
                        MemberIntentsRow.member_id == MemberRow.id,
                        combine(*[c.is_(True) for c in cols]),
                    )
                )
            )
    if f.has_entry is not None:
        ent = exists().where(MemberEntryRow.member_id == MemberRow.id)
        stmt = stmt.where(ent if f.has_entry else ~ent)
    if f.claimed_only:
        stmt = stmt.where(claimed_subquery())
    return stmt
