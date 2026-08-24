# Members

The directory: who went through CDTM, what they did before and since, and what they are
open to. This context owns the person, the cohorts they belong to, the block each member
maintains about themselves, and the plain-words Ask over all of it. Every other board holds
member ids and comes here for the name and the face.

Code: `backend/members/`. Related decisions:
[ADR 0005](../../docs/adr/0005-member-entry-is-separate-from-the-scrape.md),
[ADR 0006](../../docs/adr/0006-natural-language-ask-translates-to-filters.md),
[ADR 0007](../../docs/adr/0007-bounded-contexts-follow-the-product-boards.md).

## Language

**Member**:
One person who went through CDTM, as this platform knows them: a roster identity plus whatever the LinkedIn scrape and their own Entry add to it. A Member exists because they are on the Roster, not because they signed in, so most Members have never used the platform.
_Avoid_: user (a person who signed in is identity's **Account**), alumnus (a current student is a Member too), contact, profile (that is the larger view of a Member, not the person)

**Member card**:
The tile-sized view of a Member: name, face, headline, class, current company and title, intents. What the directory lists, what `lookup` returns, and what every other board draws next to a member id.
_Avoid_: summary (that is the LinkedIn paragraph on the profile), row, item

**Profile**:
The whole Member: the card plus positions, educations, skills, languages, the CA block, the company block, and the Entry. Fetched when a card is opened, never in a list.
_Avoid_: detail view, full member, bio

**Roster**:
CDTM's own record of who was in which class. It is the source of the Member, the Class and the major, and it is upstream: the loader writes from it and the platform never writes back.
_Avoid_: database, directory (the directory is what we show, the roster is where the people came from), member list

**Class**:
One CDTM cohort, such as `Spring 2021`: a season, a year, an id from the roster, and a location. A Member belongs to one or more Classes.
_Avoid_: cohort in code and API names (it is the right English word and the roster says class; keeping one word keeps `class_id` and `class_label` meaning the same thing), batch, year (a year holds two classes)

**Class label**:
The printed name of a Class, `"Fall 2019"`. Denormalised onto the Member because every card shows it and nothing sorts by it.
_Avoid_: class name, cohort label

**Major**:
The roster's field of study for a Member, such as `Management & Technology`. Filtered on exactly, and offered as a facet, so it is never matched as a substring.
_Avoid_: degree (a **Education** has degrees; the major is the roster's single word for what they read at university), subject, course

**Entry**:
The block a Member maintains about themselves: what to ask them about, what they are doing now, where they are, how to reach them, hobbies and topics, and whether it is visible to members at all. Separate from the scrape by decision, so a refresh of LinkedIn never overwrites what somebody typed (ADR 0005).
_Avoid_: bio, self-description, edit (that is the act), overrides (an Entry is authored, not a patch on the scrape, even though the card prefers it)

**Visibility**:
Whether an Entry is shown to other members or hidden. A hidden Entry is still there and still the Member's; it is nulled out for everyone except that Member and an admin.
_Avoid_: private, deleted, public (the directory has no public: signing in is the floor)

**Intents**:
The six things a Member says they are open to: co-founding, mentoring, hiring, open to roles, speaking, investing, plus one short note. Filterable, and the reason "who is open to mentoring" is a question the directory can answer.
_Avoid_: interests (what someone likes is a topic on their Entry), availability, tags, preferences

**CA**:
Center Assistant: a Member who worked at the Center. A flag and a block of detail on the Member, not a separate kind of person.
_Avoid_: staff, teaching assistant, employee

**CA alumni**:
A CA who has finished. Tri-valued on purpose: unknown is not the same as currently serving.
_Avoid_: former CA in field names, inactive

**Position**:
One job in a Member's work history, from the scrape: title, company, dates, whether it is current. The Member's card shows only the current one; the history is on the profile.
_Avoid_: job (a **Job** is the job board's open role), role (a **Role** here is student, ca or faculty), experience

**Education**:
One school and degree in a Member's history, from the scrape. Together with Positions it is what a free-text question searches.
_Avoid_: study (the paths context uses "study" for the group someone's degree falls into), school (that is one field of an Education), degree (also one field)

**Role**:
What a Member was at CDTM: `student`, `ca` or `faculty`. A Member can be more than one over time.
_Avoid_: type, permission (nothing here grants anybody anything; permissions are identity's **Admin**)

**Slug**:
The stable, human-readable id a Member is addressed by in URLs, `abraham-duplaa`. Comes from the loader, is unique, and is what the frontend links to; the UUID is what other boards store.
_Avoid_: handle, username (nobody chooses it and it is not a login), permalink

**Claimed member**:
A Member whose e-mail an Account has bound to (identity's **Binding**). Computed per request, never stored here: this context asks whether an account row exists for the member and puts a boolean on the card.
_Avoid_: registered, active, signed up, verified

**Roster match**:
How confidently the loader decided a roster person and a scraped tile are the same human: `matched`, `match_method`, `needs_review`. Loader bookkeeping, never member-facing. It is exposed as a `review` block on the profile and only to an admin, because the admin bind page is its one reader; `roster_person_id` is an id in a source system and does not leave the backend at all.
_Avoid_: binding (that is identity's Account to Member link, by exact e-mail, and confusing the two is how people get each other's data), confidence, verification

**Ask**:
A plain-words question about the directory, turned into a `MemberQuery` filter object and then run through the same repository search the ordinary endpoint uses. There is no path from a sentence to SQL (ADR 0006). Two translators are always available, one asking a language model and one applying keyword rules, so a missing API key degrades the answer rather than the endpoint.
_Avoid_: search (that is the ordinary filtered endpoint), chat, query in prose (a **Query** is the filter object the question becomes), AI

**Interpretation**:
How a question was read: a one-line summary, the filter object, a confidence, and the phrases that could not be mapped. Shown to the asker as editable chips, so a wrong reading is visible and fixable rather than mysterious.
_Avoid_: parse, understanding, intent (an **Intent** is one of the six flags a Member sets)

**Facets**:
The values the directory offers to filter by: the Classes, the majors, and how many Members there are. One call, because a filter bar needs all of them at once.
_Avoid_: aggregations, options, metadata

## Relationships

- A **Member** belongs to one or more **Classes**; the printed **Class label** is denormalised onto the Member and the Classes are the joined truth
- A **Member** has at most one **Entry** and at most one set of **Intents**, both written only by that Member
- A **Member** has many **Positions** and many **Educations**, all owned by the loader; nobody edits them through the API
- Where an **Entry** and the scrape disagree about the current company, title or location, the card shows the Entry: the Member is the better source on themselves
- A **Member** has at most one **Roster match**, is **Claimed** by at most one identity **Account**, and neither is visible on the card
- An **Ask** produces exactly one **Interpretation** and then an ordinary directory page; the filters it may produce are the filters the endpoint already has
- The paths context reads **Positions**, **Educations** and the **Class** through a read port and never imports these ORM models; nothing here knows the classifier exists
- A career group is not a word in this context: `study_group`, `first_step_group` and `current_group` are plain strings owned by the Paths read model, injected into the translators as vocabulary and matched against `member_paths` as text
- Deleting a **Member** cascades to their Entry, Intents, Positions and Educations, and leaves identity's Account with a null `member_id`

## Example dialogue

> **Dev:** "The scrape says they are at BMW, their **Entry** says they founded something. Which one is the card's company?"
> **Domain expert:** "The Entry. A LinkedIn refresh happens on our schedule, not theirs, and if we let it overwrite what they typed they will type it once and never again. That is the whole reason the Entry is a separate thing."

> **Dev:** "A **Member** has an e-mail, so they can sign in, so they are a user, yes?"
> **Domain expert:** "No. Most of the directory has never opened the site. A Member is a person on the **Roster**. Whether an **Account** ever binds to them is identity's business, and all we put on the card is **Claimed**."

> **Dev:** "The admin bind page wants to know how sure we were about a match. Can I put `match_method` back on the card?"
> **Domain expert:** "No. Every signed-in member reads that card. How the loader guessed that a roster line and a LinkedIn tile are the same human is bookkeeping about our import, not a fact about the person, and `roster_person_id` is an id in somebody else's system. Admins get it on the profile, under `review`, and nobody else gets it at all."

## Flagged ambiguities

- "member" and "user" were used interchangeably. Resolved: a **Member** is a person in the roster; identity's **Account** is a login. A Member with no Account is the normal case, not a broken one.
- "matching" and "binding" both described attaching a person to an e-mail. Resolved: **Roster match** is the loader's name-based guess and lives here; **Binding** is identity's exact-e-mail link from an Account to a Member. They must never be read as the same thing.
- "role" meant both a CDTM role and an open position. Resolved: **Role** is `student|ca|faculty` here, a **Position** is a job someone held, and a `Job` is the job board's open role.
- "company" is three things. Resolved: a Member's **company** is a denormalised string on the card, `company_info` is a LinkedIn snapshot of their employer, and the job board's **Company** is a curated record. `at-company` matches the string, not the Company.
- "group" was used for career groups in members code. Resolved: this context has no word for a career group. The names arrive as data from the Paths read model and are only ever compared as text.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Member | `domain/member.py` (`Member`), table `members` |
| Member card | `domain/member.py` (`Member`), `infrastructure/_mappers.py` (`to_member`), `GET /api/v1/members/` |
| Profile | `domain/member.py` (`MemberProfile`), `to_profile`, `GET /api/v1/members/{slug}` |
| Roster | `application/commands.py` (`MemberImport`, `ClassImport`), `scripts/platform/load_community.py` |
| Class | `domain/member.py` (`ClassRef`), tables `classes` and `member_classes` |
| Class label | `members.class_label`, `MemberFilters.class_label` |
| Major | `members.major`, matched exactly in `infrastructure/_member_query.py` |
| Entry | `domain/entry.py` (`MemberEntry`), table `member_entries`, `PUT /api/v1/members/me/entry` |
| Visibility | `domain/entry.py` (`Visibility`), applied in `application/member_service.py` (`_redact`) |
| Intents | `domain/entry.py` (`MemberIntents`), table `member_intents`, `PUT /api/v1/members/me/intents` |
| CA, CA alumni | `members.is_ca`, `members.ca_alumni`, `domain/member.py` (`CaDetail`), table `ca_details` |
| Position | `domain/member.py` (`Position`), table `positions` |
| Education | `domain/member.py` (`Education`), table `educations` |
| Role | `domain/member.py` (`Role`), `members.roles` |
| Slug | `members.slug`, unique; `find_id_by_slug` |
| Claimed member | `Member.is_claimed`, `infrastructure/_member_query.py` (`claimed_subquery`), correlated EXISTS over `accounts` |
| Roster match | `domain/member.py` (`RosterMatch`, `MatchMethod`), `members.matched`, `members.match_method`, `members.needs_review`; `MemberProfile.review`, nulled for non-admins in `application/member_service.py` (`_redact`) |
| `roster_person_id` | `members.roster_person_id`, `application/commands.py` (`MemberImport`), used by the loader to find an existing row and on no response model |
| Ask | `domain/ask.py` (`MemberQuery`), `application/ask_service.py`, `api/ask.py`, `POST /api/v1/members/ask/` |
| Interpretation | `domain/ask.py` (`AskInterpretation`), `POST /api/v1/members/ask/explain` |
| Translators | `infrastructure/ask_translator_llm.py`, `infrastructure/ask_translator_rules.py`, both taking `study_groups` and `career_groups` as constructor vocabulary |
| Paths vocabulary | `application/ports.py` (`MemberFilters.study_group`, `first_step_group`, `current_group`, `ViewerGroupSource`), matched as text in `_member_query.py` (`_path_group_exists`) |
| Facets | `api/members.py` (`facets`), `api/schemas.py` (`DirectoryFacets`), `GET /api/v1/members/facets` |
| Batched card reads | `GET /api/v1/members/lookup?ids=` (up to 50 ids, in order) and `GET /api/v1/members/at-company?company=` (up to 50 names, `domain/member.py` (`CompanyContact`): company, member, total) |
