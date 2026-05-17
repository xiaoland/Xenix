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
    ProblemKind,
    TrainedModelRow,
)
from xenix.services.storage.repositories import (
    DatasetRepository,
    MLTaskRepository,
    ProjectRepository,
    TrainedModelRepository,
)


def _build_session(monkeypatch, tmp_path: Path) -> Session:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    return context.session_factory()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _create_project(session: Session) -> ProjectRow:
    project = ProjectRow(name="Retail")
    ProjectRepository().create(session, project)
    return project


def _create_source_dataset(session: Session, project: ProjectRow, tmp_path: Path) -> DatasetRow:
    dataset_file = tmp_path / "customers.csv"
    dataset_file.write_text("age,income,label\n30,9000,1\n41,12000,0\n", encoding="utf-8")
    dataset = DatasetRow(
        project_id=project.id,
        name="Customers",
        source_path=str(dataset_file.resolve()),
        source_format=DatasetSourceFormat.CSV,
        copied_from=None,
        copied_at=None,
        ml_task_id=None,
    )
    DatasetRepository().create(session, dataset)
    return dataset


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


def test_dataset_repository_provenance_queries(monkeypatch, tmp_path: Path) -> None:
    datasets = DatasetRepository()
    output_file = tmp_path / "predictions.csv"
    output_file.write_text("feature,prediction\n1,0\n", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        source_dataset = _create_source_dataset(session, project, tmp_path)
        task = MLTaskRow(
            project_id=project.id,
            dataset_id=source_dataset.id,
            task_type=MLTaskType.INFERENCE,
            status=MLTaskStatus.SUCCEEDED,
        )
        MLTaskRepository().create(session, task)
        copied_dataset = DatasetRow(
            project_id=project.id,
            name="Customers copy",
            source_path=str((tmp_path / "copy.csv").resolve()),
            source_format=DatasetSourceFormat.CSV,
            copied_from=source_dataset.id,
            copied_at=_utc_now(),
            ml_task_id=None,
        )
        generated_dataset = DatasetRow(
            project_id=project.id,
            name="Predictions",
            source_path=str(output_file.resolve()),
            source_format=DatasetSourceFormat.CSV,
            copied_from=None,
            copied_at=None,
            derived_from_dataset_id=None,
            ml_task_id=task.id,
        )
        derived_dataset = DatasetRow(
            project_id=project.id,
            name="Customers cleaned",
            source_path=str((tmp_path / "cleaned.csv").resolve()),
            source_format=DatasetSourceFormat.CSV,
            copied_from=None,
            copied_at=None,
            derived_from_dataset_id=source_dataset.id,
            ml_task_id=None,
        )
        datasets.create(session, copied_dataset)
        datasets.create(session, generated_dataset)
        datasets.create(session, derived_dataset)
        session.commit()

        sources = datasets.list_source_by_project(session, project.id)
        generated = datasets.list_generated_by_project(session, project.id)
        copies = datasets.list_copies_by_source(session, source_dataset.id)
        derived = datasets.list_derived_by_source(session, source_dataset.id)
        by_task = datasets.get_by_ml_task(session, task.id)

    assert [row.id for row in sources] == [source_dataset.id]
    assert [row.id for row in generated] == [generated_dataset.id, derived_dataset.id]
    assert [row.id for row in copies] == [copied_dataset.id]
    assert [row.id for row in derived] == [derived_dataset.id]
    assert by_task is not None
    assert by_task.id == generated_dataset.id


def test_ml_task_repository_round_trip_by_dataset(monkeypatch, tmp_path: Path) -> None:
    ml_tasks = MLTaskRepository()

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        dataset = _create_source_dataset(session, project, tmp_path)
        task = MLTaskRow(
            project_id=project.id,
            dataset_id=dataset.id,
            task_type=MLTaskType.FIT,
            status=MLTaskStatus.PENDING,
            request_payload={"model": "regression.ridge"},
        )
        ml_tasks.create(session, task)
        session.commit()

        loaded = ml_tasks.get(session, task.id)
        listed = ml_tasks.list_by_dataset(session, dataset.id)

    assert loaded is not None
    assert loaded.request_payload["model"] == "regression.ridge"
    assert [row.id for row in listed] == [task.id]


def test_ml_task_completion_persists_artifacts(monkeypatch, tmp_path: Path) -> None:
    ml_tasks = MLTaskRepository()
    artifact_path = tmp_path / "model.pkl"
    artifact_path.write_text("binary-placeholder", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        dataset = _create_source_dataset(session, project, tmp_path)
        task = MLTaskRow(
            project_id=project.id,
            dataset_id=dataset.id,
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


def test_trained_model_repository_round_trip_by_dataset(monkeypatch, tmp_path: Path) -> None:
    trained_models = TrainedModelRepository()
    artifact_path = tmp_path / "canonical-model.joblib"
    artifact_path.write_text("binary-placeholder", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        dataset = _create_source_dataset(session, project, tmp_path)
        task = MLTaskRow(
            project_id=project.id,
            dataset_id=dataset.id,
            task_type=MLTaskType.FIT,
            status=MLTaskStatus.SUCCEEDED,
        )
        MLTaskRepository().create(session, task)
        trained_model = TrainedModelRow(
            dataset_id=dataset.id,
            ml_task_id=task.id,
            model_key="regression.ridge",
            problem_kind=ProblemKind.REGRESSION,
            artifact_path=str(artifact_path),
            metadata_payload={"saved_name": "Demand · Ridge Regression · 2026-04-24 09:30"},
        )
        trained_models.create(session, trained_model)
        session.commit()

        loaded = trained_models.get(session, trained_model.id)
        by_task = trained_models.get_by_ml_task(session, task.id)
        listed = trained_models.list_by_dataset(session, dataset.id)
        loaded_payload = dict(loaded.metadata_payload) if loaded is not None else {}
        trained_models.update_metadata(
            session,
            trained_model.id,
            {"saved_name": "Demand · Ridge Regression · 2026-04-24 09:35"},
            _utc_now(),
        )
        session.commit()
        refreshed = trained_models.get(session, trained_model.id)

    assert loaded is not None
    assert loaded.artifact_path == str(artifact_path)
    assert loaded_payload["saved_name"] == "Demand · Ridge Regression · 2026-04-24 09:30"
    assert by_task is not None
    assert by_task.id == trained_model.id
    assert [row.id for row in listed] == [trained_model.id]
    assert refreshed is not None
    assert refreshed.metadata_payload["saved_name"] == "Demand · Ridge Regression · 2026-04-24 09:35"
