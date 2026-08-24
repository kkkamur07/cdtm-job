"""Validating a response model from the domain object, rather than from a dump of it.

Four routers used to write ``XPublic.model_validate(obj.model_dump())``. That is two full
passes over the whole answer: the dump serialises every field and every nested model down
to primitives, and the validator then builds all of them again. ``XPublic`` subclasses the
domain model, so reading the fields off the instance is one pass and is the same body.

"Is the same body" is the part worth a test rather than a claim, so each of these builds a
real object and compares the JSON of the two ways of getting there.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.housing.api.schemas import HousingAskInterpretationPublic
from backend.housing.domain import HousingAskInterpretation, HousingQuery
from backend.jobboard.api.schemas import JobAskInterpretationPublic
from backend.jobboard.domain import JobAskInterpretation, JobQuery
from backend.members.api.schemas import AskAnswerPublic, AskInterpretationPublic
from backend.members.domain import AskAnswer, AskInterpretation, Member, MemberQuery
from backend.paths.api.schemas import PathFlowPublic
from backend.paths.domain import PathFlow, PathLink, PathNode


def _members_interpretation() -> AskInterpretation:
    return AskInterpretation(
        summary="People who studied physics and went into consulting",
        filters=MemberQuery(q="physics", study_group="Natural Sciences & Math", limit=20),
        confidence=0.8,
        unresolved=["the word 'recently'"],
        source="rules",
    )


def _answer() -> AskAnswer:
    return AskAnswer(
        interpretation=_members_interpretation(),
        members=[
            Member(
                id=uuid4(),
                slug="ada-lovelace",
                name="Ada Lovelace",
                headline="Building things",
                class_label="Spring 2020",
                company="Plato",
                title="Founder",
                updated_at=datetime(2026, 4, 2, 9, 30, tzinfo=UTC),
            )
        ],
        total=1,
    )


def _flow() -> PathFlow:
    return PathFlow(
        members_counted=3,
        nodes=[
            PathNode(stage="study", group="Natural Sciences & Math", count=2),
            PathNode(stage="current", group="Consulting", count=1),
        ],
        links=[
            PathLink(
                source_stage="study",
                source_group="Natural Sciences & Math",
                target_stage="current",
                target_group="Consulting",
                count=1,
            )
        ],
    )


def test_a_members_ask_answer_reads_the_same_off_the_object_as_off_a_dump() -> None:
    answer = _answer()
    from_object = AskAnswerPublic.model_validate(answer, from_attributes=True)
    from_dump = AskAnswerPublic.model_validate(answer.model_dump())
    assert from_object.model_dump_json() == from_dump.model_dump_json()
    # The composed field the router fills in afterwards is untouched by either route.
    assert from_object.flow is None


def test_a_members_interpretation_reads_the_same_off_the_object_as_off_a_dump() -> None:
    interpretation = _members_interpretation()
    assert (
        AskInterpretationPublic.model_validate(
            interpretation, from_attributes=True
        ).model_dump_json()
        == AskInterpretationPublic.model_validate(interpretation.model_dump()).model_dump_json()
    )


def test_a_path_flow_reads_the_same_off_the_object_as_off_a_dump() -> None:
    flow = _flow()
    assert (
        PathFlowPublic.model_validate(flow, from_attributes=True).model_dump_json()
        == PathFlowPublic.model_validate(flow.model_dump()).model_dump_json()
    )


def test_a_job_interpretation_reads_the_same_off_the_object_as_off_a_dump() -> None:
    interpretation = JobAskInterpretation(
        summary="Remote engineering roles in Berlin",
        filters=JobQuery(q="engineer", city="Berlin", remote_only=True, sort="recent"),
        confidence=0.6,
        unresolved=[],
        source="rules",
    )
    assert (
        JobAskInterpretationPublic.model_validate(interpretation).model_dump_json()
        == JobAskInterpretationPublic.model_validate(interpretation.model_dump()).model_dump_json()
    )


def test_a_housing_interpretation_reads_the_same_off_the_object_as_off_a_dump() -> None:
    interpretation = HousingAskInterpretation(
        summary="Rooms in Munich under 900 euros",
        filters=HousingQuery(city="Munich", max_price=900, kind="offer"),
        confidence=0.9,
        unresolved=[],
        source="rules",
    )
    assert (
        HousingAskInterpretationPublic.model_validate(interpretation).model_dump_json()
        == HousingAskInterpretationPublic.model_validate(
            interpretation.model_dump()
        ).model_dump_json()
    )
