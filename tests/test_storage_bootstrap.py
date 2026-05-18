from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import (
    artifact_datasets_root,
    artifact_inference_root,
    artifact_models_root,
    artifact_training_root,
    database_path,
    ml_task_parent_root,
)
from xenix.services.storage.migrations import CURRENT_SCHEMA_VERSION, get_user_version
from xenix.services.storage.models import AgentMessageRow, AgentMessageStatus


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
    assert artifact_inference_root(paths).is_dir()
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

    assert CURRENT_SCHEMA_VERSION == 4
    assert "work_item" not in table_names
    assert "derived_from_dataset_id" in dataset_columns
    assert {"status", "updated_at", "finalized_at"}.issubset(agent_message_columns)
    assert "work_item_id" not in ml_task_columns
    assert "work_item_id" not in trained_model_columns
