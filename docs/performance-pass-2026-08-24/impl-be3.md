# Contract-level performance audit, implementation report (be3)

All four code items were validated against the current tree and implemented. Line numbers
in the "validated" paragraphs are the pre-change positions unless stated otherwise.

---

## Item 1: list summary DTOs (High)

### Validated

- `backend/jobboard/api/schemas.py:30` `class JobPublic(Job)` and `:36` `items: list[JobPublic]`.
  `backend/jobboard/domain/job.py:68` `description: str = Field(min_length=1)` with no cap on
  the aggregate, capped at `MAX_RICH_TEXT = 20_000` on the way in
  (`backend/core/text.py:15`, `backend/jobboard/application/commands.py:70`).
  `:87-89` `must_have_skills`, `nice_to_have_skills`, `languages`.
- `backend/housing/api/schemas.py:13,22` and `backend/housing/domain/housing.py:33`
  `description: str | None = None`.
- `backend/events/api/schemas.py:10,17` and `backend/events/domain/events.py:27`
  `description: str | None = None`.
- Page size is 100 (`backend/core/api/pagination.py:17`), and the frontend asks for exactly
  that: `frontend/src/app/(app)/jobs/page.tsx:33` `limit: 100`,
  `frontend/src/app/(app)/housing/page.tsx:24` `limit: 100`,
  `frontend/src/api/server.ts:110` events `limit: 100`.

Frontend re-verified by grep across `frontend/src` (excluding `schema.d.ts`):

- `description` appears only on detail pages and forms:
  `src/app/(app)/jobs/[slug]/page.tsx:132`, `src/app/(app)/housing/[id]/page.tsx:164`,
  `src/app/(app)/events/[id]/Client.tsx:52`, plus the three create forms and the housing
  edit form. No list row, card, or feed panel reads it.
- `must_have_skills` / `nice_to_have_skills`: only `src/app/(app)/jobs/[slug]/page.tsx:141,152`
  and `src/app/(app)/jobs/new/Client.tsx`. `languages` on jobs: nowhere
  (`src/features/community/ask/filters.ts:40,155` is the *members* Ask filter object).
- Client-side filtering confirmed to be id- and facet-only:
  `JobsBrowser.tsx:126-162` intersects the Ask answer by `job.id` and searches
  `${job.title} ${job.company} ${job.location}`; facets are `employmentType`,
  `workArrangement`, `experienceLevel`, `city` (all on `JobRowData`).
  `HousingBrowser.tsx:71-105` intersects by `listing.id` and filters on `kind`/`city`.
  Home feed (`src/app/(app)/page.tsx:124`) builds rows through `toJobRow` and
  `EventRow ... compact`, neither of which touches a description.

### Changed

Backend:

- `backend/jobboard/api/schemas.py`: new `JobSummaryPublic` (all `Job` fields except the
  four above; `from_attributes=True`). `JobsPublic.items` now `list[JobSummaryPublic]`.
  The `salary_min`/`salary_max` `field_serializer` delegates to `Job._plain_salary`, so a
  row and the detail page cannot disagree about whether a salary carries cents.
- `backend/housing/api/schemas.py`: new `HousingListingSummaryPublic`;
  `HousingListingsPublic.items` now uses it.
- `backend/events/api/schemas.py`: new `EventSummaryPublic`; `EventsPublic.items` uses it.
- Routers build the summary straight off the domain object, no dict round trip:
  `backend/jobboard/api/jobs.py:50`, `backend/housing/api/housing.py:47`,
  `backend/events/api/events.py:28` all `SummaryPublic.model_validate(x)`.
- Detail, create and update routes are untouched and still return the full aggregate
  (`JobPublic`, `HousingListingPublic`, `EventPublic`), including `PUT /events/{id}/rsvp`,
  which the browser writes into its cache.
- Ask envelopes are list-shaped, so they were narrowed too:
  `JobAskAnswerPublic.jobs: list[JobSummaryPublic]`,
  `HousingAskAnswerPublic.listings: list[HousingListingSummaryPublic]`.
  The members `AskAnswerPublic` was left alone: `AskAnswer.members` is `list[Member]`
  (`backend/members/domain/member.py:120`), the tile-sized record, with no long-text field.
  Detail shapes untouched.

Frontend:

- `src/api/types.ts`: added `JobSummary`, `HousingListingSummary`, `CommunityEventSummary`
  next to the existing wide aliases, with a comment naming which routes return which.
- `src/api/server.ts`: `loadJobs`, `loadHousing`, `loadEvents` now return `Page<*Summary>`;
  `loadJob`, `loadJobBySlug`, `loadHousingListing`, `loadEvent` keep the wide types.
- `src/features/jobboard/jobData.ts`: `jobLocation` and `toJobRow` take `JobSummary`
  (a whole `Job` is structurally assignable, so the detail page still compiles).
- `src/api/hooks/community.ts`: `EventsPage.items` is `CommunityEventSummary[]`;
  `withRsvp` is generic over the fields it edits, so it serves both a row and a whole event.
- `src/features/community/events/EventList.tsx`, `src/app/(app)/events/Client.tsx`: row and
  RSVP control typed on the summary.

### Not done, with reason

- `CompanyPublic` / `SeekerPublic` were left as they are. The audit did not name them, and
  neither aggregate has a `MAX_RICH_TEXT` field on the list path that the UI ignores
  (`companies/page.tsx:50` reads `short_description` off the row).

### Tests

- `tests/unit/test_list_summary_dtos.py` (new, 7 tests): pins each summary's field set
  against its aggregate's minus the omitted names, so a field added to `Job`,
  `HousingListing` or `Event` fails until somebody decides whether a row carries it; and
  asserts value-for-value JSON equality on every kept field, salary normalisation included.
- `tests/integration/test_list_summaries.py` (new, 8 tests): from the outside, the three
  list routes omit the fields, the by-id / by-slug / create / patch / rsvp routes keep them,
  the two Ask answers ship rows, and all three boards still answer `{items, total}`.
- `tests/integration/test_events_gaps.py:249` adjusted: it asserted `listed["description"]`
  on a list row. The detail assertion two lines above it already covers the value, so the
  row assertion became `assert "description" not in listed` with a pointer to the new file.

---

## Item 2: `/network/saved` and `/network/intros` unbounded (Medium)

### Validated

- `backend/network/api/network.py:27-32` `@router.get("/saved", response_model=list[SavedMemberPublic])`
  and `:53-62` `@router.get("/intros", response_model=list[IntroRequestPublic])`, neither with
  `PageParamsDep`. `SqlNetworkRepository.list_saved` / `list_intros`
  (`backend/network/infrastructure/network_repository.py:17,71`) selected every row.
- `backend/core/sql.py:18` `page_with_total(session, stmt, *, skip, limit) -> tuple[list[Sequence[Any]], int]`
 : returns row tuples with the `count(*) OVER ()` stripped off the end, so a
  `select(Row)` statement yields one-element tuples. Used as `r[0]`.

### Changed

- `backend/network/infrastructure/network_repository.py`: both list methods take
  `*, skip, limit`, return `PageResult`, and go through `page_with_total`. The `ORDER BY`
  (`created_at.desc()`) and the `or_` on both intro directions are unchanged.
- `backend/network/application/ports.py`: the `NetworkRepository` protocol follows.
- `backend/network/application/network_service.py`: `list_saved` / `list_intros` take
  `*, skip, limit` and return `PageResult[...View]`. The card lookup still runs over the
  page's ids only, which is now a bounded set by construction.
- `backend/network/api/schemas.py`: new `SavedMembersPublic` and `IntroRequestsPublic`
  `{items, total}` envelopes.
- `backend/network/api/network.py`: both routes take `PageParamsDep` and return the
  envelope.

Frontend:

- `src/api/server.ts`: `loadMySaved` returns `SavedMembersPage` and asks for `limit: 100`.
- `src/api/hooks/me.ts`: one `SHORTLIST_LIMIT = 100` and one shared `savedPage` query fn
  for `useMySaved` and `useSavedIds`; `savedIds` projects `page.items`; `useMyIntros` asks
  for the same limit; `useRespondToIntro`'s optimistic edit works on `page.items`.
- `src/features/community/me/SavedList.tsx`, `me/IntrosList.tsx`,
  `members/IntroRequest.tsx`, `src/app/(app)/page.tsx`: read `.items` / `.total`.
  The home feed's "All N" now shows `saved.total` (the true count) rather than the length
  of the array it happened to receive.
- `src/api/keys.ts` untouched: the key did not have to change.

**On the limit of 100.** `PageParams` caps `limit` at 100
(`backend/core/api/pagination.py:17`), and both readers want the whole shortlist rather
than a window (the ids `Set` behind every save button, and the `/me` tab). So both ask for
the first page at the cap and read `total` for the count. A member who saved more than 100
people would see the 100 most recently saved, and their save buttons would read "not saved"
for anyone outside that window. That is the point at which these two readers need a real
pager (or a dedicated ids endpoint); it is flagged here rather than silently accepted.

### `useToggleSaved` (Low, client-swr-dedup)

`onSuccess` no longer calls `invalidateQueries(qk.mySaved)`. `PUT /network/saved/{member_id}`
returns the authoritative `SavedMemberPublic` (`backend/network/api/network.py:35`), so the
handler writes that row over the optimistic one in place, appending it if the optimistic
insert was skipped (the caller had no `member` in hand). The optimistic insert in `onMutate`
and the `onError` rollback are unchanged, and `total` moves with the items in every branch.

### Tests

- `tests/integration/test_network.py`: envelope assertions (`["total"]`, `["items"]`,
  `{"items": [], "total": 0}`).
- `tests/integration/test_network_gaps.py`: `_saved_slugs` helper; envelope assertions;
  a new `test_the_shortlist_is_paged_rather_than_however_long_it_happens_to_be` (limit,
  skip, a page past the end, and `limit=101` being a 422); the intro-list test now also
  asserts `skip=1&limit=1` returns the right single row with `total == 3`, which is what
  proves the skip and the limit reach the query rather than the response.

---

## Item 3: double pydantic work (Medium)

### Validated

- `backend/members/api/ask.py:39` `AskAnswerPublic.model_validate(answer.model_dump())`,
  `:47` `PathFlowPublic.model_validate(flow.model_dump())`,
  `:56` `AskInterpretationPublic.model_validate(interpretation.model_dump())`.
- `backend/paths/api/paths.py:57` `PathFlowPublic.model_validate(result.model_dump())`.
- `backend/members/infrastructure/_mappers.py:59` `to_member(row).model_dump()` then
  `MemberProfile(**base, ...)`. `MemberProfile` subclasses `Member`
  (`backend/members/domain/member.py:163`), so the dump serialised `Avatar`, the
  `ClassRef` list and `MemberIntents` down to dicts purely so the constructor could build
  them back. Every profile read paid it.
- Two more of the same, in files I own, that the item did not list but that are the same
  defect: `backend/jobboard/api/ask.py:38,46` and `backend/housing/api/ask.py:29,37`.

### Changed

- `backend/members/api/ask.py` and `backend/paths/api/paths.py`: `model_validate(obj,
  from_attributes=True)`. The runtime argument rather than a config change, deliberately:
  `backend/members/api/schemas.py` and `backend/paths/api/schemas.py` are outside the file
  set I own, and the flag propagates through nested models (verified).
- `backend/jobboard/api/schemas.py`, `backend/housing/api/schemas.py`: `from_attributes=True`
  on `JobAskInterpretationPublic`, `JobAskAnswerPublic`, `HousingAskInterpretationPublic`,
  `HousingAskAnswerPublic` (these files are mine), and their routers validate the object.
- `backend/members/infrastructure/_mappers.py:59`: `dict(to_member(...))` instead of
  `.model_dump()`. `dict(model)` hands over the field values as they are, so the nested
  models pass straight through instead of being serialised and rebuilt.

### Tests

- `tests/unit/test_public_dto_from_object.py` (new, 5 tests): for each site, builds a real
  domain object and asserts `model_validate(obj, from_attributes=True).model_dump_json()`
  equals `model_validate(obj.model_dump()).model_dump_json()`. This is the "identical JSON
  before and after" check, as a test rather than a throwaway script.
- `tests/unit/test_members_mappers_members_b_gaps.py`: new
  `test_the_card_half_of_a_profile_is_the_card_itself_field_for_field`: the card half of a
  profile's JSON equals the card's own, and the nested pieces are still models rather than
  the dicts a dump would have left behind.

---

## Item 4: account listing window count

### Validated

`backend/identity/infrastructure/account_repository.py:55`
`total = await self._s.scalar(select(func.count()).select_from(stmt.subquery()))` followed
by a second query for the page: the filter ran twice.

### Changed

One edit, nothing else in the file touched: the count and the page became one
`page_with_total(self._s, stmt.order_by(AccountRow.created_at.desc()), skip=skip, limit=limit)`,
with `Account.model_validate(r[0])` for the row tuples. `func` dropped from the imports
because it had no other use; `page_with_total` added.

Covered by the existing `tests/integration/test_identity_gaps.py` (admin account listing,
`unbound_only`, and the totals), which passes.

---

## Verification

Every command run from the repository root unless noted. The integration suite ran against
a database of my own (`postgresql://localhost:5432/cdtm_community_test_be3`), never the
root `.env` URL, with `tests/integration/test_migrations.py` deselected as instructed.

### `uv run poe lint`

```
Poe => ruff check backend infrastructure scripts tests
All checks passed!
```

### `uv run poe format-check`

```
Poe => ruff format --check backend infrastructure scripts tests
314 files already formatted
```

### `uv run poe test-fast`

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
572 passed, 1 skipped, 250 deselected, 1 warning in 25.78s
```

### Integration

```
DATABASE_URL=postgresql://localhost:5432/cdtm_community_test_be3 uv run pytest tests/integration \
  -m integration -q --deselect tests/integration/test_migrations.py
...
=========================== short test summary info ============================
FAILED tests/integration/test_auth.py::test_unverified_top_level_email_is_rejected
1 failed, 247 passed, 2 deselected, 1 warning in 90.89s (0:01:30)
```

**The one failure is not mine.** `backend/identity/infrastructure/jwt_verifier.py:162`
`_email_is_verified` now treats `app_metadata.provider == "google"` as proof of
verification even when the top-level `email_verified` claim is absent, so a token with a
bare `email` claim reaches `/auth/me` with a 200 and the test's `assert r.status_code != 200`
fails. That is the concurrent agent's in-flight work on the verifier (the file is modified
in the tree and is outside my file set); my only `identity` change is `list_accounts`, which
that test never touches. The rest of the suite, including every network, jobs, housing,
events, ask and paths test, passes.

Before this failure existed in isolation I also ran the affected subset on its own:

```
DATABASE_URL=... uv run pytest tests/integration/test_events_gaps.py tests/integration/test_events.py \
  tests/integration/test_network.py tests/integration/test_network_gaps.py \
  tests/integration/test_list_summaries.py tests/integration/test_housing.py \
  tests/integration/test_housing_gaps.py tests/integration/test_jobboard.py \
  tests/integration/test_identity_gaps.py -q
67 passed, 1 warning in 42.13s
```

### Contract regeneration

```
uv run poe openapi
Poe => python scripts/platform/export_openapi.py
Wrote /Users/.../frontend/openapi/openapi.json

cd frontend && npm run generate:api
🚀 openapi/openapi.json → src/api/schema.d.ts [394.3ms]
src/api/schema.d.ts 694ms
```

New component schemas present in `frontend/src/api/schema.d.ts`: `JobSummaryPublic`,
`HousingListingSummaryPublic`, `EventSummaryPublic`, `SavedMembersPublic`,
`IntroRequestsPublic`.

### `uv run poe openapi-check` (expected to fail until commit)

```
Wrote /Users/.../frontend/openapi/openapi.json
frontend/openapi/openapi.json was stale; it has just been regenerated.
Stage it and commit again: git add frontend/openapi/openapi.json
The frontend client follows: cd frontend && npm run generate:api
```

This compares against the committed spec, and the spec change is the point of the work. Not
chased.

### Frontend, from `frontend/`

```
npm run typecheck
> tsc --noEmit
(no output)

npm run lint
> eslint
(no output)

npm run build
✓ Running next.config.ts took 35ms
✓ Compiled successfully in 1860ms
✓ Generating static pages using 9 workers (21/21) in 885ms
```

---

## Files touched

Backend:

- `backend/jobboard/api/schemas.py`, `backend/jobboard/api/jobs.py`, `backend/jobboard/api/ask.py`
- `backend/housing/api/schemas.py`, `backend/housing/api/housing.py`, `backend/housing/api/ask.py`
- `backend/events/api/schemas.py`, `backend/events/api/events.py`
- `backend/network/api/schemas.py`, `backend/network/api/network.py`,
  `backend/network/application/ports.py`, `backend/network/application/network_service.py`,
  `backend/network/infrastructure/network_repository.py`
- `backend/members/api/ask.py`, `backend/members/infrastructure/_mappers.py`
- `backend/paths/api/paths.py`
- `backend/identity/infrastructure/account_repository.py` (the one change described above)

Tests:

- new: `tests/unit/test_list_summary_dtos.py`, `tests/unit/test_public_dto_from_object.py`,
  `tests/integration/test_list_summaries.py`
- edited: `tests/unit/test_members_mappers_members_b_gaps.py`,
  `tests/integration/test_network.py`, `tests/integration/test_network_gaps.py`,
  `tests/integration/test_events_gaps.py`

Frontend:

- `frontend/openapi/openapi.json`, `frontend/src/api/schema.d.ts` (regenerated only)
- `frontend/src/api/types.ts`, `frontend/src/api/server.ts`,
  `frontend/src/api/hooks/me.ts`, `frontend/src/api/hooks/community.ts`
- `frontend/src/features/jobboard/jobData.ts`,
  `frontend/src/features/community/events/EventList.tsx`,
  `frontend/src/features/community/me/SavedList.tsx`,
  `frontend/src/features/community/me/IntrosList.tsx`,
  `frontend/src/features/community/members/IntroRequest.tsx`
- `frontend/src/app/(app)/page.tsx`, `frontend/src/app/(app)/events/Client.tsx`

`frontend/src/api/keys.ts` and `frontend/src/api/hooks/jobboard.ts` needed no change.
Nothing was committed, reverted or reformatted beyond what `uv run poe format` did to the
files this change touched.
