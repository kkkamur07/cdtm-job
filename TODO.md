# TODO

Product and engineering backlog that is not yet an issue anywhere else.

Everything still on this list is blocked on something the platform does not have yet: a mail
provider, object storage credentials, an admin screen, or a person to do the reviewing. There
is no item here that is only waiting on backend code.

## Natural-language "Ask" on Members, Jobs and Housing
- Built: one endpoint per board translates a question into that board's filter object and
  runs the ordinary repository query (ADR 0006, `docs/ask.md`). The rate limit is a shared
  Postgres counter, `furnished` is a real column, and the endpoints take a `language`.
- Left to do: keep growing `tests/unit/test_ask_golden.py` (30 questions today) from every
  question Ask reads wrongly in the wild. This one is never finished; it needs real questions
  from real members, which needs the platform to be in front of them.

## Housing
- Nothing reminds an owner that a listing is about to expire. `housing_listings.expires_at`
  is set and `POST /housing/{id}/renew` works, so the missing half is a scheduled job that
  reads listings expiring in seven days and sends one e-mail per owner. Blocked on a mail
  provider and a sender address: the platform has no way to send e-mail at all today.

## Members loader
- Review `data/derived/workspace-review.csv` (31 low-confidence rows) and the 241 unmatched
  Workspace rows. `GET /api/v1/auth/accounts?unbound=true` lists the accounts waiting for a
  binding and `POST /api/v1/auth/accounts/{account_id}/bind` performs one; what is missing is an
  admin screen in `frontend/` and somebody to sit in front of it.
- Upload avatars produced by `ingest.mjs` to Supabase Storage and write the public URLs.
  Blocked on storage credentials for the bucket.
