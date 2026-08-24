# 0004. Ingest stays a Node script; the loader is Python

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: how roster and LinkedIn data become rows in `members`. It does not
  cover what a Member may then edit (see [0005](./0005-member-entry-is-separate-from-the-scrape.md)).

## Context

`frontend/scripts/ingest.mjs` is the piece of this project with the most domain knowledge per
line. It joins scraped LinkedIn JSON (`data/linkedin/05_2026/*.json`, never committed) against
four roster CSVs in `data/roster/` (`people.csv`, `classes.csv`, `students.csv`, `cas.csv`,
plus an optional `overrides.csv`) by name, and the matching is not a one-liner. The `MatchMethod`
enumeration is its output vocabulary: `exact`, `variant`, `fold`, `truncated-surname`,
`firstname-prefix`, `claim-elimination`, `ranked`, `arbitrary`, `override`. Low-confidence
joins land in `src/generated/unmatched.json` and `review.csv`, and a human pins them with
`overrides.csv`.

It also fetches avatars from the CDTM CMS rather than LinkedIn, because LinkedIn's image URLs
are signed and expire, and it resizes them with `sharp` to a 160 px and a 400 px WebP.

The merged platform needs that same data in Postgres. The obvious move was to port the
matcher to Python and delete the script.

## Decision

`ingest.mjs` stays, unchanged in role, as the matcher and renderer. It keeps writing:

- `frontend/public/data/index.json`: one tile-sized member record each, plus class and major
  facets;
- `frontend/public/profiles/<slug>.json`: the full profile;
- `frontend/public/avatars/<slug>-sm.webp` and `<slug>.webp`.

`scripts/platform/load_community.py` is a loader, not a matcher. It reads those files,
maps them onto `ClassImport` / `MemberImport` commands, and upserts through
`ImportService`. It makes no matching decisions of its own: `matched`, `match_method` and
`needs_review` are carried through from the JSON as data.

The one thing the loader computes that ingest does not is the career path: after each member
is upserted it calls `compute_member_path` and writes `member_paths`
(see [0005](./0005-member-entry-is-separate-from-the-scrape.md) for why that is a derived
projection and not member-owned data).

Avatars are, for now, still served as static files from `frontend/public/avatars/`. Moving
them to Supabase Storage is a `--avatar-base` flag away: pass the bucket's public base URL and
the loader rewrites the `/avatars/...` prefix as it writes the rows.

## Rationale

The matcher's value is its accumulated exceptions, not its algorithm. A rewrite would
reproduce the algorithm and lose the tuning, and every regression in it is a person shown
under the wrong name or class. There is no test corpus that would catch that, because the
inputs are PII that cannot be committed.

The two jobs have different lifetimes. Matching runs when someone re-scrapes LinkedIn,
perhaps twice a year, on a laptop, against files that never leave it. Loading runs on every
deployment of new data, against a database. Keeping them in one program would force the
database credential into the machine that holds the scrape.

Node is where the scrape and `sharp` already are. The frontend needs `sharp` regardless,
and the ingest output is also what the current static frontend reads, so during the port both
consumers are served by one artifact.

Alternatives considered:

- *Port the matcher to Python and drop the JSON files.* Rejected for the reasons above, and
  because it would break the still-live static frontend mid-port.
- *Have the API ingest uploaded scrapes directly.* Rejected: it puts raw LinkedIn PII on the
  server and makes a human review step (`review.csv`, `overrides.csv`) into an admin UI that
  nobody has time to build.
- *Load the JSON into a staging table and match in SQL.* Rejected: name matching in SQL is
  the same algorithm, written worse, in a language with no test harness here.

## Consequences

- The pipeline has two steps and they are run by hand, in order:
  `node scripts/ingest.mjs` then `uv run poe load-community`.
- `MemberImport` mirrors ingest's output shape field by field, including its camelCase-to-
  snake_case translation (`companyUrl` to `company_url`, `linkedInUrl` to `linkedin_url`,
  `researchFields` to `research_fields`). When `ingest.mjs` changes what it writes, both
  `frontend/src/lib/types.ts` and `MemberImport` change with it.
- The loader is idempotent: members are keyed by `slug`, classes by their roster `id`.
  Re-running it after a re-scrape updates in place and recomputes paths.
- Workspace e-mails are loaded separately (`--emails slug,email`), because they come from a
  different export than the scrape and arrive on a different schedule.
- The inputs live in `data/` at the repository root, and nothing there but `data/README.md` is
  committed; `frontend/data/`, `*.xlsx` and `05_2026/` remain in `.gitignore` as legacy
  locations. The scrape and the Workspace export are PII; nothing derived from them that names
  a person outside the roster belongs in git.
