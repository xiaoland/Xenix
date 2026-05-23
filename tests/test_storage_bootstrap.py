import json
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import (
    artifact_apply_root,
    artifact_datasets_root,
    artifact_models_root,
    artifact_training_root,
    database_path,
    ml_task_parent_root,
)
from xenix.services.storage.migrations import CURRENT_SCHEMA_VERSION, get_user_version
from xenix.services.storage.models import (
    AgentMessageAuthor,
    AgentMessageKind,
    AgentMessageRow,
    AgentMessageStatus,
    AgentThreadRow,
    MLTaskArtifactKind,
    MLTaskArtifactRow,
    MLTaskRow,
    MLTaskStatus,
    MLTaskType,
)


def _table_columns(context, table_name: str) -> set[str]:
    with context.engine.connect() as connection:
        return {
            str(row[1])
            for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").all()
        }


def test_storage_bootstrap_creates_database_and_sets_user_version(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())

    context = StorageBootstrapService().initialize(paths)

    assert context.schema_version == CURRENT_SCHEMA_VERSION
    assert database_path(paths).exists()
    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert artifact_datasets_root(paths).is_dir()
    assert artifact_models_root(paths).is_dir()
    assert artifact_training_root(paths).is_dir()
    assert artifact_apply_root(paths).is_dir()
    assert ml_task_parent_root(paths).is_dir()


def test_storage_bootstrap_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    service = StorageBootstrapService()

    first = service.initialize(paths)
    second = service.initialize(paths)

    assert get_user_version(first.engine) == CURRENT_SCHEMA_VERSION
    assert get_user_version(second.engine) == CURRENT_SCHEMA_VERSION


def test_storage_bootstrap_migrates_v1_dataset_lineage_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE dataset (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                source_path VARCHAR NOT NULL,
                source_format VARCHAR,
                copied_from VARCHAR,
                copied_at DATETIME,
                ml_task_id VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dataset (
                id,
                project_id,
                name,
                source_path,
                source_format,
                copied_from,
                copied_at,
                ml_task_id,
                created_at,
                updated_at
            )
            VALUES (
                'dataset-1',
                'project-1',
                'Customers',
                'C:/data/customers.csv',
                'csv',
                NULL,
                NULL,
                NULL,
                '2026-05-17T00:00:00Z',
                '2026-05-17T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=1")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert "derived_from_dataset_id" in _table_columns(context, "dataset")
    with context.engine.connect() as connection:
        migrated_row = connection.exec_driver_sql(
            "SELECT id, derived_from_dataset_id FROM dataset WHERE id='dataset-1'"
        ).first()
        indexes = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA index_list(dataset)").all()
        }
    assert migrated_row == ("dataset-1", None)
    assert "ix_dataset_derived_from_dataset_id" in indexes


def test_storage_bootstrap_migrates_v2_agent_message_lifecycle_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_message (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                turn_id VARCHAR,
                sequence_index INTEGER NOT NULL,
                kind VARCHAR NOT NULL,
                ui_author VARCHAR NOT NULL,
                content_blocks JSON NOT NULL,
                provider_payload JSON NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_message (
                id,
                thread_id,
                turn_id,
                sequence_index,
                kind,
                ui_author,
                content_blocks,
                provider_payload,
                created_at
            )
            VALUES (
                'message-1',
                'thread-1',
                'turn-1',
                0,
                'ASSISTANT',
                'ASSISTANT',
                '[]',
                '{}',
                '2026-05-17T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=2")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert {"status", "updated_at", "finalized_at"}.issubset(_table_columns(context, "agent_message"))
    with context.engine.connect() as connection:
        migrated_row = connection.exec_driver_sql(
            "SELECT status, updated_at, finalized_at FROM agent_message WHERE id='message-1'"
        ).first()
    with context.session_factory() as session:
        orm_row = session.get(AgentMessageRow, "message-1")
    assert migrated_row == (
        "completed",
        "2026-05-17T00:00:00Z",
        "2026-05-17T00:00:00Z",
    )
    assert orm_row is not None
    assert orm_row.status is AgentMessageStatus.COMPLETED


def test_storage_bootstrap_migrates_v3_uppercase_agent_message_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_message (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                turn_id VARCHAR,
                sequence_index INTEGER NOT NULL,
                kind VARCHAR NOT NULL,
                ui_author VARCHAR NOT NULL,
                content_blocks JSON NOT NULL,
                provider_payload JSON NOT NULL,
                status VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                finalized_at DATETIME
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_message (
                id,
                thread_id,
                turn_id,
                sequence_index,
                kind,
                ui_author,
                content_blocks,
                provider_payload,
                status,
                created_at,
                updated_at,
                finalized_at
            )
            VALUES (
                'message-1',
                'thread-1',
                'turn-1',
                0,
                'ASSISTANT',
                'ASSISTANT',
                '[]',
                '{}',
                'COMPLETED',
                '2026-05-17T00:00:00Z',
                '2026-05-17T00:00:00Z',
                '2026-05-17T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=3")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    with context.engine.connect() as connection:
        migrated_status = connection.exec_driver_sql(
            "SELECT status FROM agent_message WHERE id='message-1'"
        ).scalar_one()
    with context.session_factory() as session:
        orm_row = session.get(AgentMessageRow, "message-1")
    assert migrated_status == "completed"
    assert orm_row is not None
    assert orm_row.status is AgentMessageStatus.COMPLETED


def test_storage_bootstrap_migrates_v4_column_binding_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE dataset (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                source_path VARCHAR NOT NULL,
                source_format VARCHAR,
                copied_from VARCHAR,
                copied_at DATETIME,
                derived_from_dataset_id VARCHAR,
                ml_task_id VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute("PRAGMA user_version=4")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert {
        "dataset_id",
        "role_bindings",
        "model_key",
        "model_family",
        "model_task_kind",
        "schema_version",
        "created_at",
    }.issubset(
        _table_columns(context, "dataset_column_binding")
    )
    with context.engine.connect() as connection:
        indexes = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA index_list(dataset_column_binding)").all()
        }
    assert "ix_dataset_column_binding_dataset_id" in indexes
    assert "ix_dataset_column_binding_model_key" in indexes
    assert "ix_dataset_column_binding_model_family" in indexes
    assert "ix_dataset_column_binding_model_task_kind" in indexes


def test_storage_bootstrap_migrates_v5_turn_completion_guard_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_turn (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                sequence_index INTEGER NOT NULL,
                status VARCHAR NOT NULL,
                user_message_id VARCHAR,
                created_at DATETIME NOT NULL,
                ended_at DATETIME,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_turn (
                id,
                thread_id,
                sequence_index,
                status,
                user_message_id,
                created_at,
                ended_at,
                updated_at
            )
            VALUES (
                'turn-1',
                'thread-1',
                0,
                'open',
                NULL,
                '2026-05-20T00:00:00Z',
                NULL,
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=5")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert {"turn_id", "attempt_index", "input", "output", "created_at"}.issubset(
        _table_columns(context, "agent_turn_completion_guard")
    )
    with context.engine.connect() as connection:
        indexes = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA index_list(agent_turn_completion_guard)").all()
        }
    assert "ix_agent_turn_completion_guard_turn_id" in indexes


def test_storage_bootstrap_migrates_v6_column_selection_data_to_role_bindings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE dataset (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                source_path VARCHAR NOT NULL,
                source_format VARCHAR,
                copied_from VARCHAR,
                copied_at DATETIME,
                derived_from_dataset_id VARCHAR,
                ml_task_id VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE dataset_column_selection (
                id VARCHAR NOT NULL PRIMARY KEY,
                dataset_id VARCHAR NOT NULL,
                feature_columns JSON NOT NULL,
                target_columns JSON NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dataset (
                id,
                project_id,
                name,
                source_path,
                source_format,
                copied_from,
                copied_at,
                derived_from_dataset_id,
                ml_task_id,
                created_at,
                updated_at
            )
            VALUES (
                'dataset-1',
                'project-1',
                'Customers',
                'C:/data/customers.csv',
                'csv',
                NULL,
                NULL,
                NULL,
                NULL,
                '2026-05-20T00:00:00Z',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dataset_column_selection (
                id,
                dataset_id,
                feature_columns,
                target_columns,
                created_at
            )
            VALUES (
                'selection-1',
                'dataset-1',
                '["age", "income"]',
                '["label"]',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=6")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    with context.engine.connect() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        migrated_row = connection.exec_driver_sql(
            """
            SELECT id, dataset_id, role_bindings, model_key, model_family, model_task_kind, schema_version, created_at
            FROM dataset_column_binding
            WHERE id='selection-1'
            """
        ).first()
    assert "dataset_column_selection" not in table_names
    assert migrated_row is not None
    assert migrated_row[0] == "selection-1"
    assert migrated_row[1] == "dataset-1"
    assert migrated_row[3:7] == (None, None, None, 1)
    assert migrated_row[7] == "2026-05-20T00:00:00Z"
    assert '"role": "feature"' in migrated_row[2]
    assert '"columns": ["age", "income"]' in migrated_row[2]
    assert '"role": "target"' in migrated_row[2]
    assert '"role_kind": "single_column"' in migrated_row[2]


def test_storage_bootstrap_migrates_v7_inference_values_to_apply(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE ml_task (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                dataset_id VARCHAR,
                task_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                request_payload JSON NOT NULL,
                result_payload JSON,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE ml_task_artifact (
                id VARCHAR NOT NULL PRIMARY KEY,
                ml_task_id VARCHAR NOT NULL,
                artifact_kind VARCHAR NOT NULL,
                absolute_path VARCHAR NOT NULL,
                ready_to_open BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ml_task (
                id,
                project_id,
                dataset_id,
                task_type,
                status,
                request_payload,
                result_payload,
                error_summary,
                created_at,
                started_at,
                finished_at,
                updated_at
            )
            VALUES (
                'task-1',
                'project-1',
                'dataset-1',
                'inference',
                'succeeded',
                '{}',
                '{}',
                NULL,
                '2026-05-20T00:00:00Z',
                NULL,
                '2026-05-20T00:00:00Z',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ml_task_artifact (
                id,
                ml_task_id,
                artifact_kind,
                absolute_path,
                ready_to_open,
                created_at
            )
            VALUES (
                'artifact-1',
                'task-1',
                'inference_result',
                'C:/data/predictions.csv',
                1,
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=7")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    with context.engine.connect() as connection:
        task_type = connection.exec_driver_sql(
            "SELECT task_type FROM ml_task WHERE id='task-1'"
        ).scalar_one()
        artifact_kind = connection.exec_driver_sql(
            "SELECT artifact_kind FROM ml_task_artifact WHERE id='artifact-1'"
        ).scalar_one()
    assert task_type == "apply"
    assert artifact_kind == "apply_result"


def test_storage_bootstrap_migrates_v8_evaluation_kind_and_nullable_problem_kind(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE dataset (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                source_path VARCHAR NOT NULL,
                source_format VARCHAR,
                copied_from VARCHAR,
                copied_at DATETIME,
                derived_from_dataset_id VARCHAR,
                ml_task_id VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE ml_task (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                dataset_id VARCHAR,
                task_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                request_payload JSON NOT NULL,
                result_payload JSON,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE trained_model (
                id VARCHAR NOT NULL PRIMARY KEY,
                dataset_id VARCHAR,
                ml_task_id VARCHAR NOT NULL,
                model_key VARCHAR NOT NULL,
                problem_kind VARCHAR NOT NULL,
                artifact_path VARCHAR NOT NULL,
                metadata_payload JSON NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dataset (
                id,
                project_id,
                name,
                source_path,
                source_format,
                copied_from,
                copied_at,
                derived_from_dataset_id,
                ml_task_id,
                created_at,
                updated_at
            )
            VALUES (
                'dataset-1',
                'project-1',
                'Baskets',
                'C:/data/baskets.csv',
                'csv',
                NULL,
                NULL,
                NULL,
                NULL,
                '2026-05-20T00:00:00Z',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ml_task (
                id,
                project_id,
                dataset_id,
                task_type,
                status,
                request_payload,
                result_payload,
                error_summary,
                created_at,
                started_at,
                finished_at,
                updated_at
            )
            VALUES (
                'task-1',
                'project-1',
                'dataset-1',
                'fit',
                'succeeded',
                '{"problem_kind":"analysis","evaluation_policy":{"problem_kind":"analysis","primary_metric_name":"result_count"}}',
                '{"problem_kind":"analysis","evaluation_policy":{"problem_kind":"analysis","primary_metric_name":"result_count"}}',
                NULL,
                '2026-05-20T00:00:00Z',
                NULL,
                '2026-05-20T00:00:00Z',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO trained_model (
                id,
                dataset_id,
                ml_task_id,
                model_key,
                problem_kind,
                artifact_path,
                metadata_payload,
                created_at,
                updated_at
            )
            VALUES (
                'model-1',
                'dataset-1',
                'task-1',
                'association.apriori_apyori',
                'analysis',
                'C:/models/rules.joblib',
                '{"model_key":"association.apriori_apyori"}',
                '2026-05-20T00:00:00Z',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=8")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    with context.engine.connect() as connection:
        model_row = connection.exec_driver_sql(
            "SELECT problem_kind, metadata_payload FROM trained_model WHERE id='model-1'"
        ).first()
        task_row = connection.exec_driver_sql(
            "SELECT request_payload, result_payload FROM ml_task WHERE id='task-1'"
        ).first()
        trained_model_info = {
            str(row[1]): row
            for row in connection.exec_driver_sql("PRAGMA table_info(trained_model)").all()
        }
    assert model_row is not None
    assert model_row[0] is None
    assert json.loads(model_row[1])["evaluation_kind"] == "summary"
    assert task_row is not None
    migrated_request = json.loads(task_row[0])
    migrated_result = json.loads(task_row[1])
    assert "problem_kind" not in migrated_request
    assert migrated_request["evaluation_kind"] == "summary"
    assert migrated_request["evaluation_policy"]["evaluation_kind"] == "summary"
    assert "problem_kind" not in migrated_request["evaluation_policy"]
    assert migrated_result["evaluation_kind"] == "summary"
    assert trained_model_info["problem_kind"][3] == 0


def test_storage_bootstrap_migrates_v9_ml_task_enum_values(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE dataset (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                source_path VARCHAR NOT NULL,
                source_format VARCHAR,
                copied_from VARCHAR,
                copied_at DATETIME,
                derived_from_dataset_id VARCHAR,
                ml_task_id VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE ml_task (
                id VARCHAR NOT NULL PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                dataset_id VARCHAR,
                task_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                request_payload JSON NOT NULL,
                result_payload JSON,
                error_summary VARCHAR,
                created_at DATETIME NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE ml_task_artifact (
                id VARCHAR NOT NULL PRIMARY KEY,
                ml_task_id VARCHAR NOT NULL,
                artifact_kind VARCHAR NOT NULL,
                absolute_path VARCHAR NOT NULL,
                ready_to_open BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dataset (
                id,
                project_id,
                name,
                source_path,
                source_format,
                copied_from,
                copied_at,
                derived_from_dataset_id,
                ml_task_id,
                created_at,
                updated_at
            )
            VALUES (
                'dataset-1',
                'project-1',
                'Customers',
                'C:/data/customers.csv',
                'csv',
                NULL,
                NULL,
                NULL,
                'inspect-task',
                '2026-05-20T00:00:00Z',
                '2026-05-20T00:00:00Z'
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO ml_task (
                id,
                project_id,
                dataset_id,
                task_type,
                status,
                request_payload,
                result_payload,
                error_summary,
                created_at,
                started_at,
                finished_at,
                updated_at
            )
            VALUES (?, 'project-1', 'dataset-1', ?, ?, '{}', '{}', NULL, ?, NULL, ?, ?)
            """,
            [
                (
                    "task-1",
                    "INFERENCE",
                    "PENDING",
                    "2026-05-20T00:00:00Z",
                    "2026-05-20T00:00:00Z",
                    "2026-05-20T00:00:00Z",
                ),
                (
                    "task-2",
                    "HYPERPARAMETER_TUNING",
                    "SUCCEEDED",
                    "2026-05-20T00:00:00Z",
                    "2026-05-20T00:00:00Z",
                    "2026-05-20T00:00:00Z",
                ),
                (
                    "inspect-task",
                    "INSPECT_DATASET",
                    "SUCCEEDED",
                    "2026-05-20T00:00:00Z",
                    "2026-05-20T00:00:00Z",
                    "2026-05-20T00:00:00Z",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO ml_task_artifact (
                id,
                ml_task_id,
                artifact_kind,
                absolute_path,
                ready_to_open,
                created_at
            )
            VALUES (?, ?, ?, ?, 1, '2026-05-20T00:00:00Z')
            """,
            [
                ("artifact-1", "task-1", "INFERENCE_RESULT", "C:/data/predictions.csv"),
                ("artifact-2", "task-2", "TRAINING_REPORT", "C:/reports/training.json"),
                ("artifact-3", "inspect-task", "OTHER", "C:/reports/inspect.json"),
            ],
        )
        connection.execute("PRAGMA user_version=9")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    with context.engine.connect() as connection:
        task_rows = {
            str(row[0]): (str(row[1]), str(row[2]))
            for row in connection.exec_driver_sql(
                "SELECT id, task_type, status FROM ml_task ORDER BY id"
            ).all()
        }
        artifact_rows = {
            str(row[0]): str(row[1])
            for row in connection.exec_driver_sql(
                "SELECT id, artifact_kind FROM ml_task_artifact ORDER BY id"
            ).all()
        }
        dataset_task_id = connection.exec_driver_sql(
            "SELECT ml_task_id FROM dataset WHERE id='dataset-1'"
        ).scalar_one()

    with context.session_factory() as session:
        task = session.get(MLTaskRow, "task-1")
        artifact = session.get(MLTaskArtifactRow, "artifact-1")

    assert task_rows == {
        "task-1": ("apply", "pending"),
        "task-2": ("hyperparameter_tuning", "succeeded"),
    }
    assert artifact_rows == {
        "artifact-1": "apply_result",
        "artifact-2": "training_report",
    }
    assert dataset_task_id is None
    assert task is not None
    assert task.task_type is MLTaskType.APPLY
    assert task.status is MLTaskStatus.PENDING
    assert artifact is not None
    assert artifact.artifact_kind is MLTaskArtifactKind.APPLY_RESULT


def test_storage_bootstrap_migrates_v10_provider_request_schema_and_system_message(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_thread (
                id VARCHAR NOT NULL PRIMARY KEY,
                title VARCHAR,
                system_prompt VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE agent_turn (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                sequence_index INTEGER NOT NULL,
                status VARCHAR,
                user_message_id VARCHAR,
                created_at DATETIME NOT NULL,
                ended_at DATETIME,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE agent_message (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                turn_id VARCHAR,
                sequence_index INTEGER NOT NULL,
                kind VARCHAR,
                ui_author VARCHAR,
                content_blocks JSON NOT NULL,
                provider_payload JSON NOT NULL,
                status VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                finalized_at DATETIME
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_thread (
                id,
                title,
                system_prompt,
                created_at,
                updated_at
            )
            VALUES (
                'thread-1',
                'Analysis',
                'You are Xenix.',
                '2026-05-21T00:00:00Z',
                '2026-05-21T00:00:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_turn (
                id,
                thread_id,
                sequence_index,
                status,
                user_message_id,
                created_at,
                ended_at,
                updated_at
            )
            VALUES (
                'turn-1',
                'thread-1',
                0,
                'ended',
                'message-user',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:02:00Z',
                '2026-05-21T00:02:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_message (
                id,
                thread_id,
                turn_id,
                sequence_index,
                kind,
                ui_author,
                content_blocks,
                provider_payload,
                status,
                created_at,
                updated_at,
                finalized_at
            )
            VALUES (
                'message-user',
                'thread-1',
                'turn-1',
                0,
                'user',
                'user',
                '[{"type":"text","text":"Analyze this file"}]',
                '{}',
                'completed',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:01:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=10")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert {
        "thread_id",
        "turn_id",
        "run_id",
        "provider_name",
        "model",
        "request_kind",
        "status",
        "input_message_ids",
        "output_message_ids",
        "usage_payload",
        "created_at",
        "completed_at",
    }.issubset(_table_columns(context, "agent_provider_request"))
    with context.engine.connect() as connection:
        message_rows = connection.exec_driver_sql(
            """
            SELECT id, kind, ui_author, turn_id, sequence_index, content_blocks
            FROM agent_message
            WHERE thread_id='thread-1'
            ORDER BY sequence_index
            """
        ).all()

    assert [str(row[1]) for row in message_rows] == ["SYSTEM", "USER"]
    assert [int(row[4]) for row in message_rows] == [0, 1]
    assert str(message_rows[0][2]) == "SYSTEM"
    assert str(message_rows[0][3]) == "turn-1"
    assert json.loads(str(message_rows[0][5])) == [{"type": "text", "text": "You are Xenix."}]
    with context.session_factory() as session:
        system_message = session.get(AgentMessageRow, str(message_rows[0][0]))

    assert system_message is not None
    assert system_message.kind is AgentMessageKind.SYSTEM
    assert system_message.ui_author is AgentMessageAuthor.SYSTEM
    assert system_message.status is AgentMessageStatus.COMPLETED


def test_storage_bootstrap_migrates_v12_thread_selected_model_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_thread (
                id VARCHAR NOT NULL PRIMARY KEY,
                title VARCHAR,
                system_prompt VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_thread (id, title, system_prompt, created_at, updated_at)
            VALUES ('thread-1', 'Thread', 'Prompt', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """
        )
        connection.execute("PRAGMA user_version=12")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    assert "selected_fq_model_key" in _table_columns(context, "agent_thread")
    with context.engine.connect() as connection:
        indexes = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA index_list(agent_thread)").all()
        }
    assert "ix_agent_thread_selected_fq_model_key" in indexes
    with context.session_factory() as session:
        thread = session.get(AgentThreadRow, "thread-1")

    assert thread is not None
    assert thread.selected_fq_model_key is None


def test_storage_bootstrap_migrates_v11_message_enum_names(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    db_path = database_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE agent_message (
                id VARCHAR NOT NULL PRIMARY KEY,
                thread_id VARCHAR NOT NULL,
                turn_id VARCHAR,
                sequence_index INTEGER NOT NULL,
                kind VARCHAR,
                ui_author VARCHAR,
                content_blocks JSON NOT NULL,
                provider_payload JSON NOT NULL,
                status VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                finalized_at DATETIME
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_message (
                id,
                thread_id,
                turn_id,
                sequence_index,
                kind,
                ui_author,
                content_blocks,
                provider_payload,
                status,
                created_at,
                updated_at,
                finalized_at
            )
            VALUES (
                'message-system',
                'thread-1',
                'turn-1',
                0,
                'system',
                'system',
                '[{"type":"text","text":"You are Xenix."}]',
                '{}',
                'completed',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:01:00Z'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO agent_message (
                id,
                thread_id,
                turn_id,
                sequence_index,
                kind,
                ui_author,
                content_blocks,
                provider_payload,
                status,
                created_at,
                updated_at,
                finalized_at
            )
            VALUES (
                'message-user',
                'thread-1',
                'turn-1',
                1,
                'user',
                'user',
                '[{"type":"text","text":"Analyze this file"}]',
                '{}',
                'completed',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:01:00Z',
                '2026-05-21T00:01:00Z'
            )
            """
        )
        connection.execute("PRAGMA user_version=11")

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
    with context.engine.connect() as connection:
        rows = connection.exec_driver_sql(
            """
            SELECT id, kind, ui_author, status
            FROM agent_message
            ORDER BY sequence_index
            """
        ).all()

    assert [(str(row[1]), str(row[2]), str(row[3])) for row in rows] == [
        ("SYSTEM", "SYSTEM", "completed"),
        ("USER", "USER", "completed"),
    ]
    with context.session_factory() as session:
        system_message = session.get(AgentMessageRow, "message-system")
        user_message = session.get(AgentMessageRow, "message-user")

    assert system_message is not None
    assert system_message.kind is AgentMessageKind.SYSTEM
    assert system_message.ui_author is AgentMessageAuthor.SYSTEM
    assert system_message.status is AgentMessageStatus.COMPLETED
    assert user_message is not None
    assert user_message.kind is AgentMessageKind.USER
    assert user_message.ui_author is AgentMessageAuthor.USER


def test_storage_bootstrap_uses_ai_first_baseline_without_work_item_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())

    context = StorageBootstrapService().initialize(paths)

    with context.engine.connect() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        ml_task_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(ml_task)").all()
        }
        dataset_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(dataset)").all()
        }
        trained_model_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(trained_model)").all()
        }
        agent_message_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_message)").all()
        }
        agent_thread_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_thread)").all()
        }
        column_binding_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(dataset_column_binding)").all()
        }
        guard_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_turn_completion_guard)").all()
        }
        provider_request_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_provider_request)").all()
        }

    assert CURRENT_SCHEMA_VERSION == 13
    assert "work_item" not in table_names
    assert "dataset_column_selection" not in table_names
    assert "dataset_column_binding" in table_names
    assert "agent_turn_completion_guard" in table_names
    assert "agent_provider_request" in table_names
    assert "derived_from_dataset_id" in dataset_columns
    assert {
        "dataset_id",
        "role_bindings",
        "model_key",
        "model_family",
        "model_task_kind",
        "schema_version",
        "created_at",
    }.issubset(column_binding_columns)
    assert {"turn_id", "attempt_index", "input", "output", "created_at"}.issubset(guard_columns)
    assert {
        "thread_id",
        "turn_id",
        "run_id",
        "provider_name",
        "model",
        "request_kind",
        "status",
        "input_message_ids",
        "output_message_ids",
        "usage_payload",
        "created_at",
        "completed_at",
    }.issubset(provider_request_columns)
    assert {"status", "updated_at", "finalized_at"}.issubset(agent_message_columns)
    assert "selected_fq_model_key" in agent_thread_columns
    assert "work_item_id" not in ml_task_columns
    assert "work_item_id" not in trained_model_columns
