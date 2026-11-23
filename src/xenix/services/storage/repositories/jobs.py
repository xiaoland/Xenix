from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, col, select

from ..models import JobDomain, JobRow, JobStatus


class JobRepository:
    def find(self, session: Session, domain: JobDomain, reference: int) -> JobRow | None:
        return session.exec(
            select(JobRow).where(JobRow.domain == domain, JobRow.reference == reference)
        ).first()

    def find_by_references(
        self, session: Session, domain: JobDomain, references: Sequence[int]
    ) -> dict[int, JobRow]:
        statement = select(JobRow).where(
            JobRow.domain == domain, col(JobRow.reference).in_(references)
        )
        return {job.reference: job for job in session.exec(statement)}

    def next_queued(
        self, session: Session, domain: JobDomain, references: Sequence[int]
    ) -> JobRow | None:
        statement = (
            select(JobRow)
            .where(
                JobRow.domain == domain,
                JobRow.status == JobStatus.QUEUED,
                col(JobRow.reference).in_(references),
            )
            .order_by(col(JobRow.created_at), col(JobRow.id))
            .limit(1)
        )
        return session.exec(statement).first()

    def save(self, session: Session, job: JobRow) -> None:
        session.add(job)
