# data/

Every input dataset lives here, and nothing in this folder except this file is tracked by
git (`data/*` is ignored). All of it is personal data about CDTM members; keep it local.

```text
data/
  roster/        people.csv, classes.csv, students.csv, cas.csv, overrides.csv (optional)
                 The CDTM roster exports that ingest.mjs joins the scrape to.
  linkedin/      05_2026/*.json (one scraped LinkedIn profile per file), 05_2026.zip
                 The raw scrape. ingest.mjs reads the folder, not the zip.
  workspace/     User_Download_<date>_File.xlsx
                 The Google Workspace user export (first name, last name, e-mail, status).
  derived/       Outputs of the matchers, safe to delete and regenerate:
                   workspace-emails.csv      slug,email,method,confidence,workspace_name,
                                             member_name,status  (loader input; the loader
                                             reads slug and email, the rest is the audit trail)
                   workspace-unmatched.csv   email,workspace_name,status: Workspace rows no
                                             member matched
                   workspace-review.csv      the emails columns plus reason: low-confidence
                                             matches to check by hand
```

## Pipeline

```bash
cd frontend && node scripts/ingest.mjs            # roster + scrape -> public/data, public/profiles, avatars
cd .. && uv run poe load-community                 # JSON -> Postgres (members, positions, educations),
                                                   # then one full recompute of the paths read model
uv run poe match-emails                            # Workspace xlsx + members -> data/derived/workspace-emails.csv
uv run poe load-community --emails data/derived/workspace-emails.csv   # bind e-mails to members
```

`ingest.mjs` defaults to these paths (`../data/...` relative to `frontend/`); override with
`--data`, `--people`, `--classes`, `--students`, `--cas`, `--overrides` if a file moves.

## Rules

- Never commit anything from here, never paste rows into fixtures, docs or chat.
- Matching decisions are carried as data (`method`, `confidence`), never hidden in the loader
  (see `docs/adr/0004-ingest-stays-a-node-script-loader-in-python.md`).
- The Workspace export is the source of truth for who can sign in (see ADR 0001).
