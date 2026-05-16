from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.database import create_engine_for_path
from xenix.services.storage.layout import database_path
from xenix.services.storage.migrations import CURRENT_SCHEMA_VERSION, get_user_version, run_migrations
from xenix.services.storage.models import (
    DatasetRow,
    DatasetSourceFormat,
    DEFAULT_AGENT_THREAD_SYSTEM_PROMPT,
    MLTaskArtifactKind,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
    ProjectRow,
    ProblemKind,
    TrainedModelRow,
    WorkItemRow,
)
from xenix.services.storage.repositories import (
    DatasetRepository,
    MLTaskRepository,
    ProjectRepository,
    TrainedModelRepository,
    WorkItemRepository,
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


def test_work_item_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    projects = ProjectRepository()
    datasets = DatasetRepository()
    work_items = WorkItemRepository()

    with _build_session(monkeypatch, tmp_path) as session:
        project = ProjectRow(name="Retail")
        projects.create(session, project)
        source_dataset = _create_source_dataset(session, project, tmp_path)
        dataset_file = tmp_path / "customers-copy.csv"
        dataset_file.write_text("age,income,label\n30,9000,1\n", encoding="utf-8")
        copied_dataset = DatasetRow(
            project_id=project.id,
            name="Customers",
            source_path=str(dataset_file.resolve()),
            source_format=DatasetSourceFormat.CSV,
            copied_from=source_dataset.id,
            copied_at=_utc_now(),
            ml_task_id=None,
        )
        datasets.create(session, copied_dataset)
        work_item = WorkItemRow(
            project_id=project.id,
            name="Churn",
            dataset_id=copied_dataset.id,
            feature_columns=["age", "income"],
            target_columns=["label"],
        )
        work_items.create(session, work_item)
        session.commit()

        loaded = work_items.get(session, work_item.id)
        listed = work_items.list_by_project(session, project.id)

    assert loaded is not None
    assert loaded.name == "Churn"
    assert loaded.dataset_id == copied_dataset.id
    assert loaded.best_trained_model_id is None
    assert loaded.feature_columns == ["age", "income"]
    assert loaded.target_columns == ["label"]
    assert [row.id for row in listed] == [work_item.id]


def test_work_item_repository_sets_best_trained_model(monkeypatch, tmp_path: Path) -> None:
    work_items = WorkItemRepository()
    ml_tasks = MLTaskRepository()
    trained_models = TrainedModelRepository()
    artifact_path = tmp_path / "canonical-model.joblib"
    artifact_path.write_text("binary-placeholder", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        copied_dataset = _create_source_dataset(session, project, tmp_path)
        work_item = WorkItemRow(
            project_id=project.id,
            name="Churn",
            dataset_id=copied_dataset.id,
            feature_columns=["age", "income"],
            target_columns=["label"],
        )
        work_items.create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
            dataset_id=copied_dataset.id,
            task_type=MLTaskType.FIT,
            status=MLTaskStatus.SUCCEEDED,
        )
        ml_tasks.create(session, task)
        trained_model = TrainedModelRow(
            work_item_id=work_item.id,
            ml_task_id=task.id,
            model_key="regression.ridge",
            problem_kind=ProblemKind.REGRESSION,
            artifact_path=str(artifact_path),
        )
        trained_models.create(session, trained_model)

        updated = work_items.set_best_trained_model(session, work_item.id, trained_model.id, _utc_now())
        session.commit()

        loaded = work_items.get(session, work_item.id)

    assert updated is not None
    assert loaded is not None
    assert loaded.best_trained_model_id == trained_model.id


def test_dataset_repository_provenance_queries(monkeypatch, tmp_path: Path) -> None:
    datasets = DatasetRepository()
    output_file = tmp_path / "predictions.csv"
    output_file.write_text("feature,prediction\n1,0\n", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        source_dataset = _create_source_dataset(session, project, tmp_path)
        work_item = WorkItemRow(
            project_id=project.id,
            name="Inference",
            dataset_id=source_dataset.id,
            feature_columns=["age"],
            target_columns=["label"],
        )
        WorkItemRepository().create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
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
            ml_task_id=task.id,
        )
        datasets.create(session, copied_dataset)
        datasets.create(session, generated_dataset)
        session.commit()

        sources = datasets.list_source_by_project(session, project.id)
        generated = datasets.list_generated_by_project(session, project.id)
        copies = datasets.list_copies_by_source(session, source_dataset.id)
        by_task = datasets.get_by_ml_task(session, task.id)

    assert [row.id for row in sources] == [source_dataset.id]
    assert [row.id for row in generated] == [generated_dataset.id]
    assert [row.id for row in copies] == [copied_dataset.id]
    assert by_task is not None
    assert by_task.id == generated_dataset.id


def test_ml_task_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    ml_tasks = MLTaskRepository()

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        copied_dataset = _create_source_dataset(session, project, tmp_path)
        work_item = WorkItemRow(
            project_id=project.id,
            name="Churn",
            dataset_id=copied_dataset.id,
            feature_columns=["age", "income"],
            target_columns=["label"],
        )
        WorkItemRepository().create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
            dataset_id=copied_dataset.id,
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
    ml_tasks = MLTaskRepository()
    artifact_path = tmp_path / "model.pkl"
    artifact_path.write_text("binary-placeholder", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        copied_dataset = _create_source_dataset(session, project, tmp_path)
        work_item = WorkItemRow(
            project_id=project.id,
            name="Churn",
            dataset_id=copied_dataset.id,
            feature_columns=["age", "income"],
            target_columns=["label"],
        )
        WorkItemRepository().create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
            dataset_id=copied_dataset.id,
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


def test_trained_model_repository_round_trip(monkeypatch, tmp_path: Path) -> None:
    trained_models = TrainedModelRepository()
    artifact_path = tmp_path / "canonical-model.joblib"
    artifact_path.write_text("binary-placeholder", encoding="utf-8")

    with _build_session(monkeypatch, tmp_path) as session:
        project = _create_project(session)
        copied_dataset = _create_source_dataset(session, project, tmp_path)
        work_item = WorkItemRow(
            project_id=project.id,
            name="Churn",
            dataset_id=copied_dataset.id,
            feature_columns=["age", "income"],
            target_columns=["label"],
        )
        WorkItemRepository().create(session, work_item)
        task = MLTaskRow(
            project_id=project.id,
            work_item_id=work_item.id,
            dataset_id=copied_dataset.id,
            task_type=MLTaskType.FIT,
            status=MLTaskStatus.SUCCEEDED,
        )
        MLTaskRepository().create(session, task)
        trained_model = TrainedModelRow(
            work_item_id=work_item.id,
            ml_task_id=task.id,
            model_key="regression.ridge",
            problem_kind=ProblemKind.REGRESSION,
            artifact_path=str(artifact_path),
            metadata_payload={"saved_name": "Churn · Ridge Regression · 2026-04-24 09:30"},
        )
        trained_models.create(session, trained_model)
        session.commit()

        loaded = trained_models.get(session, trained_model.id)
        by_task = trained_models.get_by_ml_task(session, task.id)
        listed = trained_models.list_by_work_item(session, work_item.id)
        loaded_payload = dict(loaded.metadata_payload) if loaded is not None else {}
        trained_models.update_metadata(
            session,
            trained_model.id,
            {"saved_name": "Churn · Ridge Regression · 2026-04-24 09:35"},
            _utc_now(),
        )
        session.commit()
        refreshed = trained_models.get(session, trained_model.id)

    assert loaded is not None
    assert loaded.artifact_path == str(artifact_path)
    assert loaded_payload["saved_name"] == "Churn · Ridge Regression · 2026-04-24 09:30"
    assert by_task is not None
    assert by_task.id == trained_model.id
    assert [row.id for row in listed] == [trained_model.id]
    assert refreshed is not None
    assert refreshed.metadata_payload["saved_name"] == "Churn · Ridge Regression · 2026-04-24 09:35"


def test_run_migrations_upgrades_v4_trained_model_table_to_current(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    engine = create_engine_for_path(database_path(paths))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE trained_model (
                id TEXT PRIMARY KEY,
                work_item_id TEXT NOT NULL,
                ml_task_id TEXT NOT NULL UNIQUE,
                model_key TEXT NOT NULL,
                problem_kind TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql("PRAGMA user_version=4")

    version = run_migrations(engine)

    with engine.connect() as connection:
        columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(trained_model)").all()
        }

    assert version == get_user_version(engine)
    assert get_user_version(engine) == CURRENT_SCHEMA_VERSION
    assert "metadata_payload" in columns


def test_run_migrations_upgrades_v7_agent_threads_with_system_prompt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    engine = create_engine_for_path(database_path(paths))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_thread (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO agent_thread (id, title, created_at, updated_at)
            VALUES ('thread-1', 'Legacy thread', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        connection.exec_driver_sql("PRAGMA user_version=7")

    version = run_migrations(engine)

    with engine.connect() as connection:
        columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_thread)").all()
        }
        prompt = connection.exec_driver_sql(
            "SELECT system_prompt FROM agent_thread WHERE id='thread-1'"
        ).scalar_one()

    assert version == CURRENT_SCHEMA_VERSION
    assert "system_prompt" in columns
    assert prompt == DEFAULT_AGENT_THREAD_SYSTEM_PROMPT


def test_run_migrations_upgrades_v8_turn_schema_and_removes_turn_end_rows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    engine = create_engine_for_path(database_path(paths))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_thread (
                id TEXT PRIMARY KEY,
                title TEXT,
                system_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_turn (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                sequence_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                user_message_id TEXT,
                end_message_id TEXT,
                created_at TEXT NOT NULL,
                ended_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_message (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                turn_id TEXT,
                sequence_index INTEGER NOT NULL,
                kind TEXT NOT NULL,
                ui_author TEXT NOT NULL,
                content_blocks JSON NOT NULL,
                provider_payload JSON NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_tool_call (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                turn_id TEXT NOT NULL,
                request_message_id TEXT NOT NULL,
                result_message_id TEXT,
                tool_name TEXT NOT NULL,
                status TEXT NOT NULL,
                arguments_payload JSON NOT NULL,
                result_payload JSON,
                error_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO agent_thread (id, title, system_prompt, created_at, updated_at)
            VALUES ('thread-1', 'Legacy thread', 'Must call turn_end if input is needed.', '2026-01-01', '2026-01-01')
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO agent_turn (
                id, thread_id, sequence_index, status, user_message_id, end_message_id,
                created_at, ended_at, updated_at
            )
            VALUES ('turn-1', 'thread-1', 0, 'ended', 'message-user', 'message-result', '2026-01-01', '2026-01-01', '2026-01-01')
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO agent_message (
                id, thread_id, turn_id, sequence_index, kind, ui_author,
                content_blocks, provider_payload, created_at
            )
            VALUES
                ('message-user', 'thread-1', 'turn-1', 0, 'user', 'user', '[{"type":"text","text":"hi"}]', '{}', '2026-01-01'),
                ('message-request', 'thread-1', 'turn-1', 1, 'tool_call', 'tool', '[{"type":"turn_end"}]', '{}', '2026-01-01'),
                ('message-result', 'thread-1', 'turn-1', 2, 'tool_call_result', 'tool', '[{"type":"tool_result_payload","payload":{"turn_end":true}}]', '{}', '2026-01-01')
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO agent_tool_call (
                id, thread_id, turn_id, request_message_id, result_message_id,
                tool_name, status, arguments_payload, result_payload, error_summary,
                created_at, updated_at
            )
            VALUES (
                'tool-call-1', 'thread-1', 'turn-1', 'message-request', 'message-result',
                'turn_end', 'succeeded', '{}', '{"turn_end": true}', NULL,
                '2026-01-01', '2026-01-01'
            )
            """
        )
        connection.exec_driver_sql("PRAGMA user_version=8")

    version = run_migrations(engine)

    with engine.connect() as connection:
        turn_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_turn)").all()
        }
        remaining_messages = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT id FROM agent_message").all()
        }
        tool_call_count = connection.exec_driver_sql("SELECT COUNT(*) FROM agent_tool_call").scalar_one()
        prompt = connection.exec_driver_sql(
            "SELECT system_prompt FROM agent_thread WHERE id='thread-1'"
        ).scalar_one()

    assert version == CURRENT_SCHEMA_VERSION
    assert "end_message_id" not in turn_columns
    assert remaining_messages == {"message-user"}
    assert tool_call_count == 0
    assert prompt == DEFAULT_AGENT_THREAD_SYSTEM_PROMPT
