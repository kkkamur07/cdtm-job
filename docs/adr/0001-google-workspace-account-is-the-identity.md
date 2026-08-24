# 0001. The Google Workspace account is the identity

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: who may sign in, what an Account is, and how an Account is attached
  to a Member. It does not cover authorization inside the app (see `backend/identity/CONTEXT.md`)
  or how the Member rows themselves are produced (see [0004](./0004-ingest-stays-a-node-script-loader-in-python.md)).

## Context

The Community Tool is a directory of everyone who has ever been through CDTM. Membership is
defined by the Roster, not by a login: a 2011 alumna is a Member whether or not she ever
opens the tool. So the tool has two populations that do not coincide, and the whole identity
design is about the gap between them.

CDTM runs a Google Workspace on `cdtm.com`, and mailboxes are not revoked when a student
finishes a class. The Workspace export taken for this project lists 1,225 active accounts
against 1,399 roster rows. Roughly 175 people in the directory therefore have no way to
sign in at all, and a handful of Workspace accounts (shared mailboxes, role addresses) map to
no roster row.

The predecessor tool sidestepped this with a shared password in front of a static export
(`Gate.tsx`, PBKDF2 hash in a committed JSON file). That is a UX gate, not access control:
every profile JSON and avatar was publicly fetchable, and there was no notion of *who* was
looking, so nothing could be personal (no saved people, no intro requests, no "my entry").

## Decision

One `cdtm.com` Google Workspace account is one Account, and an Account binds to at most one
Member. The binding key is the e-mail address.

- Supabase Auth with the Google provider issues the token. The API never sees a password.
- `AuthSettings.allowed_email_domains` (default `cdtm.com`) is checked on every request, on
  the verified claims. A token from any other domain is a 403, not a 401: the token is
  genuine, the person is simply not in this community.
- On first sight of a verified `sub`, the API upserts a row in `accounts`
  (`SqlAccountRepository.upsert_from_claims`). No pre-provisioning, no invite flow.
- If the Account has no `member_id` yet, `AuthService.authenticate` looks for a member whose
  `members.email` matches, and binds it. Binding is a one-time write; afterwards the lookup
  is skipped.
- An Account with no Member can read the directory but cannot write anything member-owned.
  `get_current_member_principal` turns that into a 403 with a hint rather than a silent empty
  page.
- Admins bind the leftovers by hand: `POST /api/v1/auth/accounts/{id}/bind` takes a member
  slug.

## Rationale

The Workspace is already the roster of who can be reached. Every alternative we considered
re-implements a membership check that IT already runs, and runs it worse.

E-mail is the only key both sides can agree on. Roster rows carry names and class ids;
LinkedIn scrapes carry names and URLs; Workspace carries e-mail. Name matching is exactly
what `ingest.mjs` already does at load time, with a review file for its failures, and doing
it *again at login* would mean a person's identity depends on a fuzzy match that can silently
change between deploys.

Alternatives considered:

- *Fuzzy-match the signing-in person to a roster row.* Rejected. A wrong match hands one
  person another person's Entry, saved list and intro requests. A missed match is recoverable
  by an admin in seconds; a wrong match may never be noticed.
- *Magic links to any address.* Rejected. It would admit anyone who claims to be an alum,
  and there is no second signal to check them against.
- *LinkedIn OAuth.* Tempting, because the scrape is LinkedIn data and the join would be exact.
  Rejected: it makes a third party the gatekeeper of a CDTM-internal directory, LinkedIn's
  API terms do not support this use, and roughly a fifth of the roster has no usable LinkedIn
  presence.
- *Keep the shared password.* Rejected by the product goal. Nothing personal can be built on
  an anonymous session.

## Consequences

- About 175 Members will never have an Account under the current Workspace policy. The
  directory shows them; they cannot edit their own Entry. `Member.is_claimed` exposes the
  difference so the UI can say so honestly.
- `members.email` is the load-bearing column. It is populated by the loader from the
  Workspace export (`load_community.py --emails slug,email`), not by the LinkedIn scrape.
  Until that export is loaded, almost nobody binds automatically. This is tracked in `TODO.md`.
- `accounts.member_id` is `UNIQUE`: two Accounts cannot claim the same Member. The FK is
  `ON DELETE SET NULL`, so re-loading the roster can never orphan a login.
- The API accepts both HS256 (legacy Supabase project secret) and asymmetric JWKS tokens,
  because a Supabase project may be on either and the choice is not ours
  (`SupabaseJwtVerifier`, `alg` in the header decides).
- `AUTH_ADMIN_EMAILS` bootstraps the first admins from the environment, because there is no
  way to promote an admin before one exists.
