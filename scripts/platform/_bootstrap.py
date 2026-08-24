"""Make ``backend`` and ``infrastructure`` importable when a script runs from anywhere."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def ensure_repo_on_path() -> Path:
    if not (REPO_ROOT / "backend").is_dir() or not (REPO_ROOT / "infrastructure").is_dir():
        raise RuntimeError(f"cannot find backend/ and infrastructure/ under {REPO_ROOT}")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return REPO_ROOT
