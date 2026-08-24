"""Who may see what on the job board, and who may change it.

Three of the board's fields are not the same for everybody: a Job's Status decides whether
the posting is on the board at all, its Compensation disclosure decides whether the salary
travels with it, and both the list reply, the detail reply and the Ask over the board return
Jobs. A rule that only one of those three applies is a rule that leaks through the other two,
which is why it lives here rather than as a private method of one service. Housing keeps its
one such rule the same way, in ``backend/housing/application/visibility.py``.

The management rules are here for the same reason: a Job, a Seeker and a Company each answer
"may this caller change it" slightly differently, and the three answers belong next to each
other rather than scattered across three services.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TypeVar

from backend.core.actor import Actor
from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import (
    Company,
    CompensationDisclosure,
    Job,
    JobStatus,
    JobSummary,
    Seeker,
)

#: The board's list hands back ``JobSummary`` and every other read hands back ``Job``. Both
#: carry the poster, the status and the compensation disclosure, which is everything the
#: rules below read, so they answer the same for either and give back what they were given.
AnyJob = TypeVar("AnyJob", Job, JobSummary)


def _owns(owner_member_id: object, actor: Actor | None) -> bool:
    """True only when the caller is a bound Member and the row names that Member.

    Both sides are nullable: a Job outlives its poster's directory row, and an Account need
    not be bound to a Member at all. Comparing them directly would make a null poster and an
    unbound Account match each other, which is exactly how an Account with no Member came to
    be able to delete anybody's posting.
    """
    if actor is None or actor.member_id is None:
        return False
    return owner_member_id == actor.member_id


def _is_admin(actor: Actor | None) -> bool:
    return actor is not None and actor.is_admin


# ---- jobs ----------------------------------------------------------------------------


def can_manage_job(job: Job | JobSummary, actor: Actor | None) -> bool:
    return _is_admin(actor) or _owns(job.posted_by_member_id, actor)


def can_see_job(job: Job | JobSummary, actor: Actor | None) -> bool:
    """Only a published Job is on the board. Its poster and an admin also see the others."""
    return job.status == JobStatus.PUBLISHED or can_manage_job(job, actor)


def job_filters_for(filters: JobFilters, actor: Actor | None) -> JobFilters:
    """Pin the board to published rows unless the caller is asking for their own postings.

    An admin sees the board as it is. A member listing their own postings
    (``posted_by_member_id`` is their own id) needs their drafts back, because that filter is
    what "my postings" is. Everybody else gets the board the public sees, whatever ``status``
    they asked for.
    """
    if _is_admin(actor) or _owns(filters.posted_by_member_id, actor):
        return filters
    return replace(filters, status=JobStatus.PUBLISHED)


def job_for_viewer(job: AnyJob, actor: Actor | None) -> AnyJob:
    """Drop the salary unless the disclosure is public, or the caller posted the Job.

    ``confidential`` and ``undisclosed`` are the poster's answer to "may we print what this
    pays", and storing that answer while returning the numbers anyway makes the field a
    decoration. Null rather than absent, so the response shape does not change with the
    reader.
    """
    if job.compensation_disclosure == CompensationDisclosure.PUBLIC or can_manage_job(job, actor):
        return job
    return job.model_copy(update={"salary_min": None, "salary_max": None, "salary_currency": None})


# ---- seekers and companies -----------------------------------------------------------


def can_manage_seeker(seeker: Seeker, actor: Actor | None) -> bool:
    return _is_admin(actor) or _owns(seeker.member_id, actor)


def seeker_for_viewer(seeker: Seeker, actor: Actor | None) -> Seeker:
    """Hide how to reach a Seeker from everybody but that Seeker and an admin.

    A Seeker profile exists to be read, but the mailbox, the phone number and the CV behind
    it are the parts a member cannot take back once a directory of them has been scraped. The
    board still shows who is looking, for what, and with which skills; a Company that wants
    to talk to one asks them through the directory. Same rule, same reason, as
    ``MemberService._redact`` nulling a Member's e-mail.
    """
    if can_manage_seeker(seeker, actor):
        return seeker
    return seeker.model_copy(update={"email": None, "phone": None, "resume_url": None})


def can_manage_company(company: Company, actor: Actor | None) -> bool:
    """A Company is shared: whoever curated the record may correct it, and so may an admin.

    Deleting one is admin-only and lives in the service, because a Company cascades to its
    Jobs and those belong to other people.
    """
    return _is_admin(actor) or _owns(company.created_by_member_id, actor)
