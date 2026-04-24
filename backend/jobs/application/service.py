from typing import Any
from uuid import UUID

from analytics.events import track_job_published_stub
from mail.job_events import on_job_published_email_stub
from jobs.application.commands import CreateJobCommand, UpdateJobCommand
from jobs.application.integration_config import IntegrationConfig
from jobs.infrastructure.repository import SupabaseJobRepository
from slack.job_publish import SlackJobPublishNotifier


class JobService:
    """Application use cases for jobs (orchestration only — no HTTP)."""

    def __init__(
        self,
        repository: SupabaseJobRepository,
        *,
        slack_notifier: SlackJobPublishNotifier | None = None,
        integrations: IntegrationConfig | None = None,
    ) -> None:
        self._repository = repository
        self._slack = slack_notifier
        self._integrations = integrations

    def create_job(self, command: CreateJobCommand) -> UUID:
        job_id = self._repository.insert_job_with_locations(command)
        self._after_publish(job_id)
        return job_id

    def update_job(self, job_id: UUID, command: UpdateJobCommand) -> None:
        self._repository.update_job(job_id, command)
        self._after_publish(job_id)

    def delete_job(self, job_id: UUID) -> bool:
        return self._repository.delete_job(job_id)

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        return self._repository.get_job_by_id(job_id)

    def list_published_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._repository.list_published_jobs(limit=limit)

    def _after_publish(self, job_id: UUID) -> None:
        row = self._repository.get_job_by_id(job_id)
        if not row or row.get("status") != "published":
            return
        company_id = UUID(str(row["company_id"]))
        title = str(row["title"])
        slug = str(row["slug"])
        if self._slack:
            self._slack.notify_published_job(
                job_id=job_id,
                company_id=company_id,
                title=title,
                job_slug=slug,
            )
        on_job_published_email_stub(self._integrations, row)
        track_job_published_stub(self._integrations, row)
