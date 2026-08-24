# 0005. A Member's Entry is separate from the scrape

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: which rows the loader may overwrite and which rows belong to the
  Member, and how the two are combined for display. It builds on
  [0004](./0004-ingest-stays-a-node-script-loader-in-python.md).

## Context

The domain session that produced `backend/community/CONTEXT.md` flagged "profile" as a word
doing three jobs at once: the LinkedIn source file, the person, and what the directory shows.
It resolved to three words: the LinkedIn data is the scrape, the person is the Member, and
what is shown is the Entry.

That is not only vocabulary. The scrape is rewritten wholesale every time someone re-runs
`ingest.mjs`, and it is derived from a source CDTM does not control. If a Member's own words
lived in the same row, the next load would delete them, and a stale LinkedIn headline would
outrank the sentence the Member wrote yesterday.

The product goal also asks for things LinkedIn simply does not have: what someone is open to
right now (co-founding, mentoring, hiring, speaking, investing), what they will happily be
asked about, how they prefer to be contacted, whether they want to be listed at all.

## Decision

Two sets of tables, with different owners and different lifetimes.

Loader-owned (rewritten by `load_community.py`, never written through the API):

| Table        | Contents                                                    |
| ------------ | ----------------------------------------------------------- |
| `classes`    | Roster cohorts, keyed by the roster's own id                |
| `members`    | Roster identity plus the LinkedIn snapshot                  |
| `member_classes` | Which classes a Member belongs to                       |
| `positions`  | LinkedIn position history                                   |
| `educations` | LinkedIn education history                                  |
| `ca_details` | Center Assistant details from the CDTM CMS                  |

Member-owned (written only through `/api/v1/community/me/...`, never touched by the loader):

| Table            | Contents                                                            |
| ---------------- | ------------------------------------------------------------------- |
| `member_entries` | `ask_me_about`, `about`, current title and company, location, contact preference, hobbies, topics, visibility |
| `member_intents` | Six booleans plus a short note                                      |

Derived (recomputed, owned by neither): `member_paths`, written by the loader from
`compute_member_path`, and `members.search_text`, rebuilt from both sides.

Where the two overlap, the Entry wins. `_mappers.to_member` resolves it field by field:

```python
location=(entry.location if entry and entry.location else row.location),
company=(entry.current_company if entry and entry.current_company else row.current_company),
title=(entry.current_title if entry and entry.current_title else row.current_title),
```

An empty Entry field falls through to the scrape rather than blanking the tile.

## Rationale

Different write authority needs different rows. "The loader may truncate this" and "only
this person may change this" cannot both be true of one column, and encoding the distinction
in application code instead of the schema means one careless upsert erases what someone wrote.

Deleting a re-scrape must be safe. With the split, `load_community.py` can be re-run at any
time, with a partial dataset, without a member noticing.

The Member-owned side is the point of the product. Intents are the difference between a
directory and a place to start collaborations; they are also the only data here that nobody
can scrape.

Alternatives considered:

- *One `members` table with nullable override columns.* Rejected: the loader's upsert would
  have to enumerate the columns it is allowed to touch, and every new column is a chance to
  get that list wrong.
- *Version the scrape and diff it.* Rejected as far more machinery than the problem needs;
  nobody has asked to see what a LinkedIn profile said last year.
- *Let members edit the scrape directly and stop re-loading.* Rejected: the scrape's value is
  that it covers the roughly 175 Members who cannot sign in at all (ADR 0001) and will never
  write an Entry.

## Consequences

- `members.search_text` is a denormalised haystack over both sides (name, headline, company,
  title, major, class, location, skills, entry topics and hobbies, position history). It is
  rebuilt by `build_search_text` on both loader upsert and entry upsert, and searched with
  `ILIKE '%q%'` over a `gin_trgm_ops` index.
- Visibility is an Entry field, not a Member field. `Visibility.HIDDEN` removes the Entry from
  what other people see (`MemberService._redact`); it does not remove the Member from the
  roster, because roster membership is not the Member's to opt out of.
- `Member.is_claimed` is computed at read time from `exists (select 1 from accounts where
  member_id = ...)`, not stored. It tells the UI whether the person behind a tile can answer.
- `PATCH`-style semantics on the Entry: `EntryUpsert` and `IntentsUpsert` use optional fields
  so an unset field is left alone rather than nulled.
- The tile a member sees is assembled server-side. There is no client-side merge to keep in
  step with `_mappers.py`.
