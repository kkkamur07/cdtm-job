#!/usr/bin/env python3
"""Export the OpenAPI schema to frontend/openapi/openapi.json (sorted keys, stable diff)."""

from __future__ import annotations

import json
import os
import sys

from _bootstrap import ensure_repo_on_path


def main() -> int:
    root = ensure_repo_on_path()
    # The schema must not depend on local secrets; ensure docs are enabled.
    os.environ.setdefault("APP_ENVIRONMENT", "development")
    # The committed schema is the superset the frontend generates types from, so the
    # development login routes are exported too (the frontend's "dev" auth mode calls them).
    # Forced on, with a throwaway signing secret, so every exporter writes the same file no
    # matter what their .env says. Production never registers these routes: the flag is
    # refused at boot there, and the frontend's "supabase" mode never calls them.
    os.environ["AUTH_DEV_LOGIN_ENABLED"] = "true"
    os.environ.setdefault("SUPABASE_JWT_SECRET", "openapi-export-only-secret-not-for-runtime")
    from backend.core.app import create_app

    output = root / "frontend" / "openapi" / "openapi.json"
    schema = create_app().openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
