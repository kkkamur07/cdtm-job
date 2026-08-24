from __future__ import annotations

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    ref: str


class ErrorResponse(BaseModel):
    error: ErrorBody
