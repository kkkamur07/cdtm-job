"""Helpers to move data between pydantic models and ORM rows."""

from __future__ import annotations

from typing import Any

from pydantic import AnyUrl, BaseModel


def dump_for_db(model: BaseModel, *, exclude_unset: bool = False) -> dict[str, Any]:
    """``model_dump`` in python mode with URL types flattened to ``str``.

    Python mode keeps ``Decimal``/``date``/``UUID`` intact (what the DB driver wants)
    but pydantic URL objects are not DB-API types, so they are stringified here.
    """
    data = model.model_dump(mode="python", exclude_unset=exclude_unset)
    return {k: (str(v) if isinstance(v, AnyUrl) else v) for k, v in data.items()}
