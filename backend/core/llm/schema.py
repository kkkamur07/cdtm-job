"""Turn a pydantic model into a JSON schema a provider will accept in strict mode.

OpenAI's ``response_format: {"type": "json_schema", ..., "strict": true}`` accepts only a
subset of JSON Schema: ``type``, ``properties``, ``required``, ``additionalProperties``,
``items``, ``enum``, ``anyOf``, ``$ref``, ``$defs``, ``description``, ``title``. It also
requires that *every* property is listed in ``required`` and that every object sets
``additionalProperties: false``. Pydantic emits the opposite of both: optional fields are
left out of ``required``, and constraints such as ``maxLength`` ride along.

So the fields stay optional in the wire sense by being nullable, and the numeric/string
constraints stay where they belong: on the pydantic model, which is what actually decides
whether the model's answer is acceptable.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

#: Validation keywords that are correct JSON Schema but rejected in strict mode. They are
#: dropped from the advertised schema only; the pydantic model still enforces them.
_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "multipleOf",
        "pattern",
        "uniqueItems",
    }
)


def _nullable(node: dict[str, Any]) -> dict[str, Any]:
    """Allow ``null`` for a property, so "the model left this out" has a representation."""
    if "anyOf" in node:
        if not any(sub.get("type") == "null" for sub in node["anyOf"]):
            node["anyOf"].append({"type": "null"})
        return node
    if "$ref" in node:
        # A bare $ref cannot carry a sibling type, so wrap it.
        ref = node.pop("$ref")
        description = node.pop("description", None)
        node["anyOf"] = [{"$ref": ref}, {"type": "null"}]
        if description is not None:
            node["description"] = description
        return node
    kind = node.get("type")
    if isinstance(kind, str) and kind != "null":
        node["type"] = [kind, "null"]
    elif isinstance(kind, list) and "null" not in kind:
        node["type"] = [*kind, "null"]
    return node


def _walk(node: Any, *, nullable_properties: bool) -> Any:
    if isinstance(node, list):
        return [_walk(n, nullable_properties=nullable_properties) for n in node]
    if not isinstance(node, dict):
        return node

    out = {k: v for k, v in node.items() if k not in _UNSUPPORTED_KEYWORDS}
    for key in ("items", "additionalProperties"):
        if key in out and isinstance(out[key], dict):
            out[key] = _walk(out[key], nullable_properties=nullable_properties)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in out:
            out[key] = _walk(out[key], nullable_properties=nullable_properties)

    for container in ("properties", "$defs"):
        if container in out and isinstance(out[container], dict):
            out[container] = {
                name: _walk(sub, nullable_properties=nullable_properties)
                for name, sub in out[container].items()
            }

    if "properties" in out:
        if nullable_properties:
            out["properties"] = {name: _nullable(sub) for name, sub in out["properties"].items()}
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


def strict_json_schema(model: type[BaseModel], *, nullable_properties: bool = True) -> dict:
    """``model.model_json_schema()`` rewritten to satisfy strict structured output."""
    return _walk(model.model_json_schema(), nullable_properties=nullable_properties)
