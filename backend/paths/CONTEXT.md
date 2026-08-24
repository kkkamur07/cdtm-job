# Paths

Where a member studied, what they did first after CDTM, where they are now, and what they
are open to. This context owns none of those facts: it reads the jobs and degrees the
members context stores, files each person under a coarse group, and keeps the verdict as a
read model so three thousand careers can be drawn as one picture.

Code: `backend/paths/`. Related decisions:
[ADR 0007](../../docs/adr/0007-bounded-contexts-follow-the-product-boards.md) for why this
is a context of its own rather than a corner of the directory, and
[ADR 0006](../../docs/adr/0006-natural-language-ask-translates-to-filters.md) for the Ask
that draws a Flow over the members its question matched.

## Language

**Member path**:
One member's row in the read model: their Study group, their First step (group, title and company), their Current group (group, title and company), and when it was computed. Derived by the Classifier from positions, educations and class dates, never typed by a person. Losing the table costs a Recompute, not data.
_Avoid_: career, journey, profile (a profile belongs to the members context and is edited by its owner; a path is a verdict about them)

**Stage**:
One of the four columns of the picture, in the order a career runs: `study`, `first_step`, `current`, `intent`. The first three are history. The fourth is not a career step at all, which is why it is built separately and why only the first three can be browsed.
_Avoid_: step (a First step is one particular stage), phase, column (that is the drawing, not the thing being drawn)

**Group**:
The coarse box a member lands in at one Stage. The groups are a fixed vocabulary decided in advance, not something the data invents: a name that is not in the list matches nobody, which is what makes a group safe to put in a filter chip or hand to a language model.
_Avoid_: category, bucket, cluster (nothing is clustered here, the boxes are named up front)

**Study group**:
What a member studied, as one of seven names (`Business & Management`, `Computer Science`, `Engineering`, `Natural Sciences & Math`, `Medicine & Life Sciences`, `Law & Social Sciences`, `Other`). Decided from the roster major first and then from each non-CDTM degree in turn.
_Avoid_: major (the major is one raw string on the member row and is one of the inputs), field, subject

**First step**:
The first real job after the class ended: the earliest dated position that is not a CDTM role, not a student or internship role, and did not start before the class was over. It is the answer to "what do people do straight out of CDTM", so a working student job held during the class is not one.
_Avoid_: first job (people had jobs before), entry role, starting position

**Current group**:
Where a member is now, from the position they still hold. People often hold several at once (founder, advisor, board seat), so the one the Classifier can actually name wins over one that would land in `Other`.
_Avoid_: current job (there may be three), employer, latest role

**Intent stage**:
The fourth column: what members say they are open to, drawn from `member_intents` as `Co-founding`, `Mentoring`, `Hiring`, `Open to roles`, `Speaking`, `Investing`, and `Not stated` for everyone who has set nothing. It is where the picture stops being history and becomes something a member can act on.
_Avoid_: availability, offers, status (the members context already uses "intents" for the same six flags, and this is that data seen as a column)

**Flow**:
The whole aggregate picture: how many members were counted, a Node for every group that has anybody in it, and a Link for every hop between two adjacent stages. The two history hops (study to first step, first step to current) count members. The links into the Intent stage count what people are open to, so a member with three intents contributes three links and those counts deliberately do not add up to the number of people.
_Avoid_: sankey (that is the chart the frontend draws with it), graph, funnel (nobody is dropping out)

**Classifier**:
The keyword rules that turn one Career history into one Member path. It lives in infrastructure because it encodes how our LinkedIn scrape reads (English and German titles, CDTM class dates), not what a career is. Group names are matched at a word start, and the first group in the list that matches wins, so the generic leadership titles under `Corporate (by role)` only ever get their chance after every more specific group has passed.
_Avoid_: matcher, tagger, model (there is no model here, and the Ask's translator is the thing that talks to one)

**Career history**:
The whole of what this context is given about a person: their major, their class year and season, four fields of each job (title, company, start date, whether it is current) and two of each degree (school, degree). Read through the `CareerHistorySource` port. Keeping it this narrow is what stops a rule quietly depending on a field it was never handed.
_Avoid_: member data, CV, resume

**Card**:
The thirteen columns needed to draw a member inside a box of the picture: name, slug, headline, avatar, class, major, current company and title. Not a second model of a Member; the full profile is one call away at `GET /api/v1/members/{slug}`.
_Avoid_: member, profile, tile

**Recompute**:
Reclassifying and upserting a path. One member after an edit, or everybody after an import. Always a full pass for everybody rather than an incremental one, because the Classifier's keyword tables change more often than the scrape does, and after editing them the only honest thing to do is redo every verdict.
_Avoid_: refresh, sync, rebuild index

## Relationships

- A **Member path** belongs to exactly one member, by `member_id`, which is also its primary key: one row per member, or none if nothing could be computed
- Deleting a member deletes their **Member path** (`ON DELETE CASCADE`); deleting a path costs nothing but a **Recompute**
- A **Member path** has at most one **Group** per **Stage**, and any of them may be null: someone with no dated jobs has no **First step**
- A **Flow** is built out of many **Member paths** plus the intents behind the fourth column; it is never stored
- Only `study`, `first_step` and `current` open into people through `GET /api/v1/paths/members`. The **Intent stage** does not, because the directory already answers "who is open to mentoring" with a filter of its own
- The **Classifier** reads a **Career history** and nothing else, and returns a **Member path** and nothing else. It performs no I/O
- This context reads the member tables and never writes to them, never imports `backend.members`, and nothing in members knows the **Classifier** exists
- The members context's Ask asks this context one question, "what group is the person asking in now", through the `ViewerGroupSource` port, and passes the ids its question matched back as a **Flow** filter

## Example dialogue

> **Dev:** "Someone changed jobs. Do we update their **Member path**?"
> **Domain expert:** "You **Recompute** it. The row is a verdict about their history, not something anybody edits. If the answer comes out different, the answer was always going to be different."

> **Dev:** "She was a working student at BMW during the class, then joined McKinsey. Which is the **First step**?"
> **Domain expert:** "McKinsey. The question the column answers is what people do once CDTM is over, and a job held while studying is not that. Anything starting before the class ended is skipped, and so is anything that says student, intern or CDTM."

> **Dev:** "The **Intent stage** counts add up to more than the number of members. Is that a bug?"
> **Domain expert:** "No, that is the column doing its job. Somebody can be open to mentoring and hiring and speaking at once, and each of those is a link. The three career columns count people; that one counts offers. The people who have said nothing are in **Not stated** so no box quietly loses them."

## Flagged ambiguities

- "group" collided with the members context, where a directory filter also speaks of study and career groups. Resolved: the names are this context's vocabulary (`STUDY_GROUP_NAMES`, `CAREER_GROUP_NAMES`), and members receives them as injected strings it never interprets.
- "intent" is a members word (six booleans a member sets about themselves) and a paths word (a column of the picture). Resolved: the members context owns the fact, this context owns the **Intent stage** that draws it, and the labels here are display text (`Co-founding`) rather than the members context's filter values (`cofounding`).
- "current" meant both "the position they still hold" and "the latest row we scraped". Resolved: **Current group** comes from a position flagged as current, preferring one the **Classifier** can name over one that would land in `Other`.
- "member" here is never the members context's `Member`. Resolved: this context knows a **Card** and a `member_id`, and reaches both through read-only handles on the member tables.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Member path | `domain/paths.py` (`MemberPath`), table `member_paths` |
| Stage | `domain/paths.py` (`STAGES`); `_STAGE_COLUMNS` and `_CAREER_HOPS` in `infrastructure/paths_repository.py` |
| Group | `domain/paths.py` (`StudyGroup`, `CareerGroup`, `STUDY_GROUP_NAMES`, `CAREER_GROUP_NAMES`) |
| Study group | `member_paths.study_group`; `STUDY_GROUPS` and `classify_study` in `infrastructure/paths_classifier.py` |
| First step | `member_paths.first_step_group`, `.first_step_title`, `.first_step_company`; `_is_cdtm_or_student` and `_class_end` decide what counts |
| Current group | `member_paths.current_group`, `.current_title`, `.current_company` |
| Intent stage | `domain/paths.py` (`INTENT_GROUPS`, `NO_INTENT_GROUP`), `SqlPathRepository._intent_stage`, read from `member_intents` |
| Flow | `domain/paths.py` (`PathFlow`, `PathNode`, `PathLink`), `GET /api/v1/paths/flow` |
| Classifier | `infrastructure/paths_classifier.py` (`compute_member_path`), injected as the `PathClassifier` port in `api/deps.py` |
| Career history | `domain/history.py` (`CareerHistory`, `WorkEntry`, `StudyEntry`), `infrastructure/career_history.py` |
| Card | `domain/card.py` (`MemberCard`), `infrastructure/member_cards.py`, `GET /api/v1/paths/members` |
| Recompute | `application/path_service.py` (`recompute`, `recompute_all`), run by `scripts/platform/load_community.py` after an import |
| Reading the member tables | `infrastructure/_member_tables.py`: `sqlalchemy.table()` handles that carry no metadata, so Alembic never sees a second mapping of `members`, `positions`, `educations`, `classes`, `member_classes` or `member_intents` |
| One member's path | `GET /api/v1/paths/members/{slug}`, which was `GET /api/v1/community/members/{slug}/path` |
