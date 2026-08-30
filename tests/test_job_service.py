from __future__ import annotations

from datetime import datetime, timedelta, timezone

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.job_service import JobDomain, JobQueryService, JobStatus
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    DatasetRow,
    DatasetSourceFormat,
    KnowledgeImportRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    ProjectRow,
)


def test_job_query_projects_and_filters_domain_authorities(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    now = datetime.now(timezone.utc)
    with storage.session_factory() as session:
        session.add(ProjectRow(id="project-1", name="Forecasting"))
        session.commit()
        session.add(
            DatasetRow(
                id="dataset-1",
                project_id="project-1",
                name="Quarterly sales",
                source_path="sales.csv",
                source_format=DatasetSourceFormat.CSV,
            )
        )
        session.commit()
        session.add(
            MLTaskRow(
                id="ml-1",
                project_id="project-1",
                dataset_id="dataset-1",
                task_type=MLTaskType.FIT,
                status=MLTaskStatus.RUNNING,
                updated_at=now,
            )
        )
        session.commit()
        session.add(
            KnowledgeImportRow(
                id="import-1",
                original_file_name="Policy.pdf",
                source_format="pdf",
                status="failed",
                phase="parsing",
                error_code="parse_failed",
                error_summary="Unsupported table",
                updated_at=now - timedelta(minutes=1),
            )
        )
        session.commit()

    service = JobQueryService(storage.session_factory)
    jobs = service.list_jobs()

    assert [job.reference for job in jobs] == ["ml:ml-1", "knowledge:import:import-1"]
    assert jobs[0].domain is JobDomain.ML
    assert jobs[0].target == "Quarterly sales"
    assert jobs[0].status is JobStatus.RUNNING
    assert jobs[1].status is JobStatus.FAILED
    assert jobs[1].error_summary == "Unsupported table"
    assert service.list_jobs(domain=JobDomain.KNOWLEDGE, search="policy") == [jobs[1]]
    assert service.list_jobs(status=JobStatus.RUNNING) == [jobs[0]]
    assert sum(job.active for job in jobs) == 1
    assert sum(job.status is JobStatus.FAILED for job in jobs) == 1
    storage.engine.dispose()


def test_job_query_maps_pending_ml_status_to_queued(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    with storage.session_factory() as session:
        session.add(ProjectRow(id="project-1", name="Forecasting"))
        session.commit()
        session.add(
            MLTaskRow(
                id="ml-pending",
                project_id="project-1",
                dataset_id=None,
                task_type=MLTaskType.FIT,
                status=MLTaskStatus.PENDING,
            )
        )
        session.commit()

    jobs = JobQueryService(storage.session_factory).list_jobs()

    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.QUEUED
    assert jobs[0].active
    storage.engine.dispose()


def test_job_query_normalizes_completed_knowledge_states(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    with storage.session_factory() as session:
        session.add(
            KnowledgeImportRow(
                id="import-ready",
                original_file_name="Ready.txt",
                source_format="txt",
                status="retrieval_ready",
                phase="completed",
            )
        )
        session.commit()

    jobs = JobQueryService(storage.session_factory).list_jobs()

    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.SUCCEEDED
    storage.engine.dispose()
