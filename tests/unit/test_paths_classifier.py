from datetime import date
from uuid import uuid4

from backend.paths.domain import CareerHistory, StudyEntry, WorkEntry
from backend.paths.infrastructure.paths_classifier import (
    CAREER_GROUPS,
    STUDY_GROUPS,
    classify_career,
    classify_study,
    compute_member_path,
)


def test_classify_study_prefers_major_keywords() -> None:
    assert classify_study([], "Management & Technology") == "Business & Management"
    assert (
        classify_study([StudyEntry(school="TUM", degree="MSc Informatics")], None)
        == "Computer Science"
    )
    assert classify_study([], None) is None


def test_classify_career_groups_titles_and_companies() -> None:
    assert classify_career("Co-Founder & CEO", "Plato") == "Founder"
    assert classify_career("Associate", "McKinsey & Company") == "Consulting"
    assert classify_career("Software Engineer", "Google") == "Big Tech"
    # generic function titles fall back to Corporate; titles that say nothing stay Other
    assert classify_career("Analyst", "Some Unknown GmbH") == "Corporate"
    assert classify_career("Barista", "Some Unknown GmbH") == "Other"


def test_first_step_skips_cdtm_and_student_jobs_and_pre_class_jobs() -> None:
    member_id = uuid4()
    positions = [
        WorkEntry(
            title="Co-Founder", company="Plato", start_date=date(2023, 8, 1), is_current=True
        ),
        WorkEntry(
            title="Venture Building", company="McKinsey & Company", start_date=date(2022, 1, 1)
        ),
        WorkEntry(title="Working Student", company="BMW", start_date=date(2020, 3, 1)),
        WorkEntry(title="Student", company="CDTM", start_date=date(2019, 10, 1)),
        WorkEntry(title="Intern", company="Siemens", start_date=date(2017, 6, 1)),
    ]
    path = compute_member_path(
        CareerHistory(
            member_id=member_id,
            major="Management & Technology",
            class_year=2019,
            class_season="Fall",
            work=positions,
            study=[],
        )
    )
    assert path.first_step_company == "McKinsey & Company"
    assert path.first_step_group == "Consulting"
    assert path.current_group == "Founder"
    assert path.study_group == "Business & Management"


def test_the_enums_cover_every_group_the_classifier_can_return() -> None:
    # The Ask filters offer these groups by name. If a group is added to the classifier
    # without adding it to the enum, questions about it silently match nothing.
    from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES

    def labels(groups: dict[str, tuple[str, ...]]) -> set[str]:
        return {name.removesuffix(" (by role)") for name in groups}

    assert labels(STUDY_GROUPS) <= set(STUDY_GROUP_NAMES)
    assert labels(CAREER_GROUPS) <= set(CAREER_GROUP_NAMES)
    # "Other" is the classifier's fallback and is never a dict key.
    assert "Other" in STUDY_GROUP_NAMES
    assert "Other" in CAREER_GROUP_NAMES
