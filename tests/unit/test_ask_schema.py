"""What the model is allowed to answer with, and how fast it may be asked."""

import pytest

from backend.core.llm.ask import ViewerContext
from backend.core.llm.rate_limit import TokenBucketLimiter
from backend.core.llm.schema import strict_json_schema
from backend.housing.domain import HousingQuery
from backend.jobboard.domain import JobQuery
from backend.jobboard.infrastructure.ask_translator_llm import build_system_prompt as job_prompt
from backend.members.domain import MemberQuery
from backend.members.infrastructure.ask_translator_llm import (
    build_system_prompt as member_prompt,
)
from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES

QUERIES = [MemberQuery, HousingQuery, JobQuery]


def _objects(node):
    """Every object schema in the document, including the ones under $defs."""
    if isinstance(node, list):
        for item in node:
            yield from _objects(item)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" or "properties" in node:
        yield node
    for value in node.values():
        yield from _objects(value)


@pytest.mark.parametrize("model", QUERIES)
def test_every_property_is_required_and_nothing_extra_is_allowed(model) -> None:
    schema = strict_json_schema(model)
    for obj in _objects(schema):
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])


@pytest.mark.parametrize("model", QUERIES)
def test_every_property_accepts_null(model) -> None:
    schema = strict_json_schema(model)
    for name, prop in schema["properties"].items():
        options = prop.get("anyOf") or [prop]
        assert any(o.get("type") == "null" for o in options), name


@pytest.mark.parametrize("model", QUERIES)
def test_unsupported_validation_keywords_are_stripped(model) -> None:
    schema = strict_json_schema(model)
    banned = {"maxLength", "minLength", "maximum", "minimum", "default", "pattern", "format"}

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            assert not banned & set(node), node
            for value in node.values():
                walk(value)

    walk(schema)


def test_member_query_still_enforces_its_own_limits() -> None:
    # The advertised schema drops the constraints; the model keeps them, which is what
    # actually decides whether an answer is usable.
    assert MemberQuery(limit=5_000).limit == 100
    assert MemberQuery(skills=[]).skills is None
    with pytest.raises(ValueError, match="extra_forbidden"):
        MemberQuery(favourite_colour="green")


def test_system_prompts_name_the_allowed_values() -> None:
    prompt = member_prompt(
        ViewerContext(class_label="Fall 2019"),
        study_groups=STUDY_GROUP_NAMES,
        career_groups=CAREER_GROUP_NAMES,
    )
    assert "Venture Capital" in prompt
    assert "Computer Science" in prompt
    assert "Fall 2019" in prompt
    assert "working_student" in job_prompt()


def test_token_bucket_allows_a_burst_then_refuses() -> None:
    limiter = TokenBucketLimiter()
    assert [limiter.allow("member-1", rate_per_minute=3) for _ in range(4)] == [
        True,
        True,
        True,
        False,
    ]
    # Buckets are per caller, so one member cannot spend another member's allowance.
    assert limiter.allow("member-2", rate_per_minute=3) is True
    limiter.reset()
    assert limiter.allow("member-1", rate_per_minute=3) is True
