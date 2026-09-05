"""Translate domain-owned progress into the shared Jobs vocabulary."""

from .storage.models import JobStatus


def knowledge_job_status(status: str) -> JobStatus:
    if status in {"pending", "queued"}:
        return JobStatus.QUEUED
    if status == "running":
        return JobStatus.RUNNING
    if status in {"failed", "needs_attention"}:
        return JobStatus.FAILED
    if status == "cancelled":
        return JobStatus.CANCELLED
    if status in {"succeeded", "canonical_ready", "retrieval_ready", "reused"}:
        return JobStatus.SUCCEEDED
    raise ValueError(f"Unrecognized Knowledge task status: {status!r}")


def ml_job_status(status: str) -> JobStatus:
    if status == "pending":
        return JobStatus.QUEUED
    if status in {"running", "succeeded", "failed", "cancelled"}:
        return JobStatus(status)
    raise ValueError(f"Unrecognized ML task status: {status!r}")
