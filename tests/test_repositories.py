from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import (
    DatasetRow,
    DatasetSourceFormat,
    MLTaskArtifactKind,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    ProjectRow,
    WorkItemRow,
)
from xenix.services.storage.repositories import (
    DatasetRepository,
    MLTaskRepository,
    ProjectRepository,
    WorkItemRepository,
)


def _build_session(monkeypatch, tmp_path: Path) -> Session:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return context.session_factory()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_project_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    repo = ProjectRepository()
    with _build_session(monkeypatch, tmp_path) as session:
        row = ProjectRow(name="Retail")
        repo.create(session, row)
        session.commit()

        loaded = repo.get(session, row.id)
        listed = repo.list_all(session)

    assert loaded is not None
    assert loaded.name == "Retail"
    assert [project.id for project in listed] == [row.id]


def test_work_item_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    projects = ProjectRepository()
    work_items = WorkItemRepository()

    with _build_session(monkeypatch, tmp_path) as session:
        project = ProjectRow(name="Retail")
        projects.create(session, project)
        work_item = WorkItemRow(project_id=project.id, name="Churn")
        work_items.create(session, work_item)
        session.commit()

        loaded = work_items.get(session, work_item.id)
        listed = work_items.list_by_project(session, project.id)

    assert loaded is not None
    assert loaded.name == "Churn"
    assert loaded.dataset_id is None
    assert loaded.feature_columns == []
    assert loaded.target_columns == []
    assert [row.id for row in listed] == [work_item.id]


def test_work_item_repository_persists_dataset_selection(monkeypatch, tmp_path: Path) -> None:
    projects = ProjectRepository()
    work_items = WorkItemRepository()
    datasets = DatasetRepository()
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,label\n30,1\n", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = ProjectRow(name="Retail")
        projects.create(session, project)
        dataset = DatasetRow(
            project_id=project.id,
            name="Customers",
            source_path=str(dataset_file.resolve()),
            source_format=DatasetSourceFormat.CSV,
        )
        datasets.create(session, dataset)
        work_item = WorkItemRow(project_id=project.id, name="Churn")
        work_items.create(session, work_item)

        updated = work_items.set_dataset_selection(
            session,
            work_item.id,
            dataset.id,
            ["age"],
            ["label"],
            _utc_now(),
        )
        session.commit()

        loaded = work_items.get(session, work_item.id)

    assert updated is not None
    assert loaded is not None
    assert loaded.dataset_id == dataset.id
    assert loaded.feature_columns == ["age"]
    assert loaded.target_columns == ["label"]


def test_dataset_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    projects = ProjectRepository()
    datasets = DatasetRepository()
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("id,name\n1,Alice\n", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = ProjectRow(name="Retail")
        projects.create(session, project)
        dataset = DatasetRow(
            project_id=project.id,
            name="Customers",
            source_path=str(dataset_file.resolve()),
            source_format=DatasetSourceFormat.CSV,
        )
        datasets.create(session, dataset)
        session.commit()

        loaded = datasets.get(session, dataset.id)
        listed = datasets.list_by_project(session, project.id)

    assert loaded is not None
    assert loaded.source_format is DatasetSourceFormat.CSV
    assert [row.id for row in listed] == [dataset.id]


def test_ml_task_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    projects = ProjectRepository()
    work_items = WorkItemRepository()
    ml_tasks = MLTaskRepository()

    with _build_session(monkeypatch, tmp_path) as session:
        project = ProjectRow(name="Retail")
        projects.create(session, project)
        work_item = WorkItemRow(project_id=project.id, name="Churn")
        work_items.create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
            task_type=MLTaskType.FIT,
            status=MLTaskStatus.PENDING,
            request_payload={"model": "regression.ridge"},
        )
        ml_tasks.create(session, task)
        session.commit()

        loaded = ml_tasks.get(session, task.id)
        listed = ml_tasks.list_by_work_item(session, work_item.id)

    assert loaded is not None
    assert loaded.request_payload["model"] == "regression.ridge"
    assert [row.id for row in listed] == [task.id]


def test_ml_task_completion_persists_artifacts(monkeypatch, tmp_path: Path) -> None:
    projects = ProjectRepository()
    work_items = WorkItemRepository()
    ml_tasks = MLTaskRepository()
    artifact_path = tmp_path / "model.pkl"
    artifact_path.write_text("binary-placeholder", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = ProjectRow(name="Retail")
        projects.create(session, project)
        work_item = WorkItemRow(project_id=project.id, name="Churn")
        work_items.create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
            task_type=MLTaskType.FIT,
            status=MLTaskStatus.RUNNING,
        )
        ml_tasks.create(session, task)
        artifact = MLTaskArtifactRow(
            ml_task_id=task.id,
            artifact_kind=MLTaskArtifactKind.MODEL,
            absolute_path=str(artifact_path),
            ready_to_open=True,
            created_at=_utc_now(),
        )

        ml_tasks.complete(
            session,
            task.id,
            {"score": 0.91},
            _utc_now(),
            [artifact],
        )
        session.commit()

        loaded = ml_tasks.get(session, task.id)
        artifacts = ml_tasks.list_artifacts(session, task.id)

    assert loaded is not None
    assert loaded.status is MLTaskStatus.SUCCEEDED
    assert loaded.result_payload == {"score": 0.91}
    assert [row.absolute_path for row in artifacts] == [str(artifact_path)]
