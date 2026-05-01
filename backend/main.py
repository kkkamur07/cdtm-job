"""ASGI entrypoint for the API.

Run from the **repository root** (where ``pyproject.toml`` lives), with the env
active::

    uv run fastapi run backend/main.py
    uv run fastapi run --workers 4 backend/main.py

Or use uvicorn directly::

    uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from backend.api.main import app

__all__ = ["app"]
