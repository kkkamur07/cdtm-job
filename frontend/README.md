CDTM Job Board frontend — [Next.js](https://nextjs.org) App Router + Tailwind. Data loads from the FastAPI backend via a generated OpenAPI client (`lib/api/generated`).

## Setup

1. Copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:8000`). The backend must allow this origin in `CORS_ORIGINS`.
2. From the **monorepo root**, refresh the OpenAPI document after API changes, then regenerate the client:

```bash
uv run python -c "import json, pathlib; from backend.api.main import app; pathlib.Path('frontend/openapi.json').write_text(json.dumps(app.openapi()))"
cd frontend && npm run openapi:generate
```

3. Run the dev server:

```bash
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Brand:** Wordmark from [cdtm.com](https://cdtm.com) CMS (`public/brand/cdtm-logo.jpg`); icon mark from [`/icon.svg`](https://cdtm.com/icon.svg) (`public/brand/cdtm-mark.svg`, `app/icon.svg`). Primary color `#0d4da1` matches the official SVG.

Typography: [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) (Inter).
