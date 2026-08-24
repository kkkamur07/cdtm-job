"""The parts of the classifier the first round of tests never made load-bearing.

``tests/unit/test_paths_classifier.py`` proves the keyword tables. What it never proves is
the *shape* of a path: which job counts as the first step after CDTM (the class-end date
boundary), which of several current roles is the one shown, and what happens when a degree
says nothing about a field of study. Every fixture there has one current role and every
student job predates the class end, so the class-end filter and the current-role preference
are both redundant for it and could be deleted without a test noticing.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from backend.paths.domain import CareerHistory, MemberPath, StudyEntry, WorkEntry
from backend.paths.infrastructure.paths_classifier import (
    classify_career,
    classify_study,
    compute_member_path,
)


def _job(
    title: str | None, company: str | None, start: date | None = None, *, current: bool = False
) -> WorkEntry:
    return WorkEntry(title=title, company=company, start_date=start, is_current=current)


def _path(
    *work: WorkEntry,
    major: str | None = None,
    study: tuple[StudyEntry, ...] = (),
    class_year: int | None = None,
    class_season: str | None = None,
) -> MemberPath:
    return compute_member_path(
        CareerHistory(
            member_id=uuid4(),
            major=major,
            class_year=class_year,
            class_season=class_season,
            work=list(work),
            study=list(study),
        )
    )


# ---- the class-end boundary -----------------------------------------------------------


def test_a_fall_class_ends_in_march_two_years_later() -> None:
    """A job taken while the class was still running is not a "first step after CDTM"."""
    path = _path(
        _job("Associate", "McKinsey & Company", date(2020, 6, 1)),
        _job("Software Engineer", "Google", date(2021, 6, 1)),
        class_year=2019,
        class_season="Fall",
    )
    assert path.first_step_company == "Google"
    assert path.first_step_title == "Software Engineer"
    assert path.first_step_group == "Big Tech"


def test_a_job_starting_on_the_day_the_class_ends_is_a_first_step() -> None:
    """The boundary is exclusive: starting *on* the end date is after the class, not during."""
    path = _path(
        _job("Associate", "McKinsey & Company", date(2021, 3, 31)),
        _job("Software Engineer", "Google", date(2021, 6, 1)),
        class_year=2019,
        class_season="Fall",
    )
    assert path.first_step_company == "McKinsey & Company"


def test_a_spring_class_ends_in_september_of_the_following_year() -> None:
    """The two seasons end at different times, and the season is read off the class row."""
    path = _path(
        _job("Associate", "Bain & Company", date(2020, 6, 1)),
        _job("Software Engineer", "Google", date(2020, 10, 15)),
        _job("Product Manager", "SAP", date(2020, 11, 20)),
        class_year=2019,
        class_season="Spring",
    )
    assert path.first_step_company == "Google"


def test_every_job_predating_the_class_end_still_yields_a_first_step() -> None:
    """Somebody who never took a job after their class still has an earliest real job."""
    path = _path(
        _job("Associate", "McKinsey & Company", date(2020, 1, 1)),
        class_year=2019,
        class_season="Fall",
    )
    assert path.first_step_company == "McKinsey & Company"
    assert path.first_step_group == "Consulting"


def test_a_student_job_is_skipped_without_ending_the_search() -> None:
    """Three rules in a row: skip the student job, skip the in-class job, take the next one."""
    path = _path(
        _job("Intern", "Google", date(2020, 1, 1)),
        _job("Associate", "McKinsey & Company", date(2020, 6, 1)),
        _job("Product Manager", "SAP", date(2022, 1, 1)),
        class_year=2019,
        class_season="Fall",
    )
    assert path.first_step_company == "SAP"


# ---- what counts as a student job -----------------------------------------------------


def test_student_intern_and_praktikum_jobs_are_never_the_first_step() -> None:
    for title in ("Student Assistant", "Intern", "Praktikant"):
        path = _path(
            _job(title, "Google", date(2020, 1, 1)),
            _job("Associate", "McKinsey & Company", date(2022, 1, 1)),
        )
        assert path.first_step_company == "McKinsey & Company", title


def test_a_cdtm_role_that_is_not_a_student_job_is_skipped_too() -> None:
    """Time at CDTM is not a step after CDTM, whatever the role was called."""
    path = _path(
        _job("Teaching Assistant", "CDTM", date(2020, 1, 1)),
        _job("Associate", "McKinsey & Company", date(2022, 1, 1)),
    )
    assert path.first_step_company == "McKinsey & Company"


def test_the_first_step_group_reads_the_title_as_well_as_the_company() -> None:
    path = _path(_job("Co-Founder", "Unknown GmbH", date(2021, 1, 1)))
    assert path.first_step_group == "Founder"
    assert path.first_step_title == "Co-Founder"
    assert path.first_step_company == "Unknown GmbH"


# ---- which of several current roles is shown ------------------------------------------


def test_the_current_role_prefers_the_one_the_classifier_can_name() -> None:
    """Founder plus working student is a founder, not a working student."""
    path = _path(
        _job("Working Student", "BMW", current=True),
        _job("Co-Founder", "Plato", current=True),
    )
    assert path.current_company == "Plato"
    assert path.current_title == "Co-Founder"
    assert path.current_group == "Founder"


def test_an_unnameable_current_role_still_beats_a_student_one() -> None:
    path = _path(
        _job("Working Student", "BMW", current=True),
        _job("Barista", "Local Cafe", current=True),
    )
    assert path.current_company == "Local Cafe"
    assert path.current_group == "Other"


def test_the_current_role_is_named_by_its_title_and_by_its_company() -> None:
    by_title = _path(
        _job("Barista", "Local Cafe", current=True),
        _job("Co-Founder", "Unknown GmbH", current=True),
    )
    assert by_title.current_title == "Co-Founder"

    by_company = _path(
        _job("Barista", "Local Cafe", current=True),
        _job("Associate", "McKinsey & Company", current=True),
    )
    assert by_company.current_company == "McKinsey & Company"
    assert by_company.current_group == "Consulting"


def test_a_member_whose_only_current_role_is_a_student_one_still_has_one() -> None:
    """Better to show the working student job than to show nothing at all."""
    path = _path(_job("Working Student", "BMW", current=True))
    assert path.current_company == "BMW"
    assert path.current_group == "Corporate"


# ---- field of study -------------------------------------------------------------------


def test_a_cdtm_degree_never_decides_the_field_of_study() -> None:
    """Everybody holds the CDTM honours degree, so it can never be what tells people apart."""
    assert (
        classify_study(
            [
                StudyEntry(school="CDTM", degree="Honours Degree in Technology Management"),
                StudyEntry(school="TUM", degree="MSc Informatics"),
            ],
            None,
        )
        == "Computer Science"
    )


def test_a_school_leaving_certificate_is_not_a_field_of_study() -> None:
    assert classify_study([StudyEntry(school="Some Gymnasium", degree="Abitur")], None) is None


def test_a_recognised_field_wins_over_an_unrecognised_one_listed_before_it() -> None:
    assert (
        classify_study(
            [
                StudyEntry(school="Foo Academy", degree="BSc Basketweaving"),
                StudyEntry(school="TUM", degree="MSc Informatics"),
            ],
            None,
        )
        == "Computer Science"
    )
    assert (
        classify_study([StudyEntry(school="Foo Academy", degree="BSc Basketweaving")], None)
        == "Other"
    )


def test_a_position_with_neither_a_title_nor_a_company_has_no_group() -> None:
    """An empty haystack is "we do not know", which is not the same answer as "Other"."""
    assert classify_career(None, None) is None
