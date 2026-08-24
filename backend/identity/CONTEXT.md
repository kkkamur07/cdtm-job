# Identity

Who is calling, and which Member they are. This context turns a Supabase Auth token into a
`Principal` that the rest of the platform can authorize against, and it owns the one column
that ties a login to a person in the directory.

Code: `backend/identity/`. Related decision:
[ADR 0001](../../docs/adr/0001-google-workspace-account-is-the-identity.md).

## Language

**Account**:
A login identity: one CDTM Google Workspace (`cdtm.com`) user, as seen by this platform. Created the first time that person signs in, never before.
_Avoid_: user, login (that is the act, not the thing), profile

**Auth user**:
Supabase Auth's own record of the same person, in the `auth` schema, which this platform does not own. An Account references it by `auth_user_id` and nothing else.
_Avoid_: account (that is ours), Supabase user in prose where "auth user" will do

**Claims**:
The fields this platform reads out of a verified access token: subject, e-mail, name, avatar, provider. Everything else in the token is ignored.
_Avoid_: token payload, JWT body

**Binding**:
Attaching an Account to exactly one Member. The key is the e-mail address. It happens once, automatically at sign-in when the e-mail matches, or by an admin afterwards.
_Avoid_: linking, matching (matching is what the ingest script does to names, and confusing the two is how people get each other's data)

**Principal**:
The authenticated caller for one request: an Account, plus the two derived facts everyone asks about, `member_id` and `is_admin`.
_Avoid_: current user, session (there is no session; every request is verified from scratch)

**Actor**:
The two facts about a Principal that a board is allowed to know: which Member is calling, and whether they are an Admin. Every board takes an Actor and no board takes a Principal, so nothing a token said can reach a domain service. Anything an Account is beyond those two facts stops at the router.
_Avoid_: current user, principal (that is this context's word and it stays here), context

**Admin**:
An Account allowed to bind other Accounts, promote other Admins, and write announcements. Bootstrapped from configuration, then promoted through the API.
_Avoid_: superuser, staff (Community uses "staff" for a role in the Roster, which is a different thing)

**Allowed domain**:
An e-mail domain permitted to sign in, `cdtm.com` by default. A valid token from outside it is refused as **not allowed**, not as **not authenticated**.
_Avoid_: whitelist

**Unbound Account**:
An Account with no Member. A normal state, not an error: it can read the directory and write nothing member-owned.
_Avoid_: orphan, invalid account

## Relationships

- An **Account** corresponds to exactly one **Auth user**, identified by `auth_user_id`, which is unique
- An **Account** binds to at most one **Member**, and a **Member** is bound by at most one **Account**
- The **Binding** is by e-mail, is written once, and survives everything: deleting a Member sets `member_id` to null rather than removing the Account
- A **Principal** exists only for the duration of one request; nothing is cached between requests except the JWKS keys
- Only an **Admin** may bind an Account or promote another **Admin**, and only an Admin may
  list the **Unbound Accounts** waiting for one
- An Account whose e-mail is outside every **Allowed domain** never becomes a **Principal**, however valid its token

## Example dialogue

> **Dev:** "The token is signed correctly but the e-mail is `@gmail.com`. Is that a 401?"
> **Domain expert:** "No. Their credential is fine, they are just not in this community. That is a 403, and retrying will not help them."

> **Dev:** "Do we create Accounts up front from the Workspace export?"
> **Domain expert:** "No. An **Account** exists because someone signed in. The export is how we learn a **Member's** e-mail, which is what the **Binding** uses; it is not a list of Accounts."

> **Dev:** "Someone changed their surname and their Workspace address changed with it. Do they get a new Account?"
> **Domain expert:** "No. The **Auth user** is the same, so the Account is the same; the e-mail is refreshed from the **Claims**. The **Binding** already exists and is not looked up again."

## Flagged ambiguities

- "user" was used for both the Supabase Auth record and our own row. Resolved: Supabase's is the **Auth user**, ours is the **Account**, and the person is Community's **Member**.
- "linking" and "matching" were used interchangeably. Resolved: **Binding** is Account to Member by exact e-mail, in this context. *Matching* is name-based, happens in `ingest.mjs`, and is never used to decide who someone is at sign-in.
- "admin" was briefly used for both a platform admin and a CDTM staff member. Resolved: **Admin** is a flag on an Account and has nothing to do with the Roster.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Account | `domain/account.py` (`Account`), table `accounts` |
| Auth user | `accounts.auth_user_id`; deliberately not a foreign key, the `auth` schema is Supabase's |
| Claims | `domain/account.py` (`TokenClaims`), produced by `infrastructure/jwt_verifier.py` |
| Binding | `application/auth_service.py` (`authenticate`, `bind_account_to_member`), `infrastructure/member_directory.py` |
| Principal | `domain/account.py` (`Principal`), `api/deps.py` (`PrincipalDep`, `MemberPrincipalDep`, `AdminPrincipalDep`) |
| Actor | `backend/core/actor.py` (`Actor`), `api/deps.py` (`ActorDep`, `MemberActorDep`, `OptionalActorDep`) |
| Admin | `accounts.is_admin`, `AUTH_ADMIN_EMAILS`, `POST /api/v1/auth/accounts/{id}/admin` |
| Allowed domain | `backend/core/settings/auth.py` (`allowed_email_domains`) |
| Unbound Account | `Principal.member_id is None`; `get_current_member_principal` is what refuses the write; `GET /api/v1/auth/accounts?unbound=true` is the admin's list of them |
