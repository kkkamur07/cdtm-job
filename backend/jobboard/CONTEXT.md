# Job Board

Companies post Jobs. People publish Seeker profiles. CDTM Members are on both sides of that,
and the platform records which ones, but the job board's language is about hiring, not about
the roster.

Code: `backend/jobboard/`. Ported from the standalone job board at `jobs.cdtm.com`; the
`/api/v1/{companies,jobs,seekers}` contract is unchanged. Related decision:
[ADR 0002](../../docs/adr/0002-one-backend-for-community-and-job-board.md).

## Language

**Company**:
An organisation that hires, as a CDTM-curated record: a name, a slug, a description, a careers page, and whether it is a CDTM startup.
_Avoid_: employer (a Job's employer is its Company, but not every employer is a Company here), organisation

**CDTM startup**:
A Company founded by CDTM Members. A flag on the Company, not a separate kind of thing, because it changes how a Job is surfaced and nothing else.
_Avoid_: alumni company, portfolio company

**Job**:
One open role at one Company: what it is, where it is, what it pays, what it needs, and whether it is currently visible.
_Avoid_: posting, listing (Housing in Community uses "listing"), vacancy, opening

**Status**:
Where a Job is in its life: `draft`, `published`, `closed`, `filled`. Only `published` is visible on the board.
_Avoid_: state, active/inactive (a `filled` Job and a `closed` Job are both inactive and mean different things)

**Poster**:
The Member who created a Job. Recorded so the board can say "posted by someone from your class"; optional, because a Job can exist without one.
_Avoid_: author, owner (nothing here grants ownership rights yet)

**Seeker**:
A job-seeking profile: who they are, what they want, what they bring, how to reach them. A Seeker may be a Member, and need not be.
_Avoid_: candidate (a candidate is someone who applied, and nobody applies through this platform), applicant, user, profile

**Employment type**:
The contractual shape of a Job: full time, part time, contract, internship, temporary, working student, freelance.
_Avoid_: contract type (`contract` is one of the values, so the phrase collides with itself)

**Work arrangement**:
Where the work happens: onsite, remote, hybrid. Separate from the Job's location, which stays meaningful for a remote role.
_Avoid_: location (that is the place), remote status

**Compensation disclosure**:
How openly the salary may be shown: `public`, `confidential`, `undisclosed`. Separate from whether a salary was recorded at all.
_Avoid_: salary visibility, transparency

## Relationships

- A **Company** has many **Jobs**; deleting a Company deletes its Jobs
- A **Job** belongs to exactly one **Company** and has at most one **Poster**
- A **Job** has exactly one **Status**, one **Employment type**, one **Work arrangement** and one **Compensation disclosure**
- A **Job** is on the board only while its Status is `published`
- A **Seeker** is one job-seeking profile and may reference at most one **Member**; a Member may have several Seeker profiles over time
- A **Seeker** does not apply to a **Job**. There is no application, no match and no message in this context
- Deleting a **Member** removes neither a **Job** nor a **Seeker**; both simply lose the reference

## Example dialogue

> **Dev:** "Is a **Seeker** just a **Member** who is looking?"
> **Domain expert:** "No. It is a document about what someone wants from a job. A **Member** is a person in the roster, and that person may write a Seeker profile, or several over the years, or none. We record which Member wrote it when we know."

> **Dev:** "A Job is filled. Do we delete it?"
> **Domain expert:** "No, set the **Status** to `filled`. `closed` means we stopped looking; `filled` means we found someone. The Company wants to know which."

> **Dev:** "This role is fully remote. What is its location?"
> **Domain expert:** "Still wherever the Company puts it, because that is the time zone, the contract and the office someone could visit. **Work arrangement** is the separate answer."

## Flagged ambiguities

- "listing" was used for both a Job and a Housing listing once the two products merged. Resolved: a **Job** in this context, a **Listing** in Community's housing.
- "company" means different things in the two contexts. Resolved: a Job Board **Company** is a curated record; a Member's employer is a denormalised LinkedIn snapshot (`members.company_info`) and is not a Company.
- "candidate" was used for a Seeker. Resolved: nobody applies through this platform, so there are no candidates. It is a **Seeker**.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Company | `domain/company.py`, table `companies` |
| CDTM startup | `companies.is_cdtm_startup` |
| Job | `domain/job.py`, table `jobs` |
| Status | `domain/job.py` (`JobStatus`), `jobs.status` with a CHECK constraint |
| Poster | `jobs.posted_by_member_id`, filled from the caller in `api/jobs.py` |
| Seeker | `domain/seeker.py`, table `seekers`, `seekers.member_id` for the overlap |
| Employment type | `domain/job.py` (`EmploymentType`) |
| Work arrangement | `domain/job.py` (`WorkArrangement`) |
| Compensation disclosure | `domain/job.py` (`CompensationDisclosure`) |
