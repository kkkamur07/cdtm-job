"""Strict structured output: the schema the provider is actually handed.

``tests/unit/test_ask_schema.py`` checks the three real query models, and every field on
them is optional, so pydantic's own output already satisfies most of what the rewriter is
for. The model below is deliberately shaped like the ones a future board will have (a
required field, a nested model, a union, a list, a mapping), which is the only way to see
what the rewriter does rather than what pydantic already did.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from backend.core.llm.schema import _walk, strict_json_schema


class Budget(BaseModel):
    currency: str
    amount: int | None = None


class Wanted(BaseModel):
    name: str
    budget: Budget = Field(description="what they can pay")
    tags: list[Annotated[str, StringConstraints(max_length=5)]] = Field(default_factory=list)
    scores: dict[str, Annotated[int, Field(le=9)]] = Field(default_factory=dict)
    mode: str | int
    note: str | None = None
    anything: Any = None


def test_the_schema_handed_to_the_provider_is_exactly_this() -> None:
    assert strict_json_schema(Wanted) == {
        "$defs": {
            "Budget": {
                "properties": {
                    # A required scalar becomes nullable in the wire sense; the pydantic
                    # model is still what decides whether the answer is acceptable.
                    "currency": {"title": "Currency", "type": ["string", "null"]},
                    # Already nullable from pydantic: left exactly as it was.
                    "amount": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "title": "Amount",
                    },
                },
                "required": ["currency", "amount"],
                "title": "Budget",
                "type": "object",
                "additionalProperties": False,
            }
        },
        "properties": {
            "name": {"title": "Name", "type": ["string", "null"]},
            # A bare $ref cannot carry a sibling type, so it is wrapped, and the field's
            # description (which is prompt text the model reads) survives the wrapping.
            "budget": {
                "anyOf": [{"$ref": "#/$defs/Budget"}, {"type": "null"}],
                "description": "what they can pay",
            },
            # maxLength is dropped from the item schema: correct JSON Schema, rejected in
            # strict mode.
            "tags": {"items": {"type": "string"}, "title": "Tags", "type": ["array", "null"]},
            "scores": {
                "additionalProperties": {"type": "integer"},
                "title": "Scores",
                "type": ["object", "null"],
            },
            # A union gains null rather than being replaced by it.
            "mode": {
                "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}],
                "title": "Mode",
            },
            "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Note"},
            # No type to make nullable: left alone rather than given one.
            "anything": {"title": "Anything"},
        },
        "required": ["name", "budget", "tags", "scores", "mode", "note", "anything"],
        "title": "Wanted",
        "type": "object",
        "additionalProperties": False,
    }


def test_every_object_in_the_document_is_closed_and_fully_required() -> None:
    schema = strict_json_schema(Wanted)
    for obj in (schema, schema["$defs"]["Budget"]):
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])


def test_the_nullable_rewrite_can_be_turned_off_without_losing_the_rest() -> None:
    schema = strict_json_schema(Wanted, nullable_properties=False)
    assert schema["properties"]["name"] == {"title": "Name", "type": "string"}
    assert schema["properties"]["budget"] == {
        "$ref": "#/$defs/Budget",
        "description": "what they can pay",
    }
    # Closing the object and requiring every property is not part of the nullable rewrite.
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(schema["properties"])
    assert "maxLength" not in schema["properties"]["tags"]["items"]


def test_a_branch_schema_is_cleaned_in_every_branch() -> None:
    """``oneOf`` and ``allOf`` are not emitted for today's models but are legal JSON Schema
    and legal in strict mode; a keyword left inside one of them is rejected by the provider
    just the same."""
    cleaned = _walk(
        {
            "type": "object",
            "properties": {
                "either": {
                    "anyOf": [
                        {"type": "object", "properties": {"a": {"type": "string"}}},
                        {"type": "string", "maxLength": 3},
                    ]
                },
                "one": {"oneOf": [{"type": "integer", "minimum": 1}]},
                "all": {"allOf": [{"type": "string", "pattern": "^x"}]},
            },
        },
        nullable_properties=True,
    )
    either = cleaned["properties"]["either"]["anyOf"]
    assert either[0] == {
        "type": "object",
        "properties": {"a": {"type": ["string", "null"]}},
        "required": ["a"],
        "additionalProperties": False,
    }
    assert either[1] == {"type": "string"}
    assert cleaned["properties"]["one"]["oneOf"] == [{"type": "integer"}]
    assert cleaned["properties"]["all"]["allOf"] == [{"type": "string"}]
    # anyOf already carried a null option? It does not, so one was added.
    assert {"type": "null"} in cleaned["properties"]["either"]["anyOf"]


def test_a_type_that_is_already_a_list_gains_null_once_and_only_once() -> None:
    """Pydantic writes a union as ``anyOf`` rather than as a type list, so today's models
    never reach this branch; it is here because a hand-written or upstream-supplied schema
    legally can, and adding ``null`` twice is as wrong as not adding it at all."""
    cleaned = _walk(
        {
            "type": "object",
            "properties": {
                "either": {"type": ["string", "integer"]},
                "already": {"type": ["string", "null"]},
                "nothing": {"type": "null"},
                "rows": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"a": {"type": "string"}}},
                },
            },
        },
        nullable_properties=True,
    )
    properties = cleaned["properties"]
    assert properties["either"]["type"] == ["string", "integer", "null"]
    assert properties["already"]["type"] == ["string", "null"]
    # A property that can only be null is already as nullable as it gets.
    assert properties["nothing"]["type"] == "null"
    # The item schema is walked too: its own properties are closed, required and nullable.
    assert properties["rows"]["items"] == {
        "type": "object",
        "properties": {"a": {"type": ["string", "null"]}},
        "required": ["a"],
        "additionalProperties": False,
    }


class Plain(BaseModel):
    budget: Budget


def test_a_reference_with_nothing_beside_it_is_wrapped_just_the_same() -> None:
    # The description is optional; the wrapping is not, because a $ref cannot carry a
    # sibling "type" and the property still has to be allowed to be null.
    assert strict_json_schema(Plain)["properties"]["budget"] == {
        "anyOf": [{"$ref": "#/$defs/Budget"}, {"type": "null"}]
    }
