from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 7


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def set_user_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={version}")


def apply_v5(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        trained_model_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(trained_model)").all()
        }
        if "metadata_payload" not in trained_model_columns:
            connection.exec_driver_sql("ALTER TABLE trained_model ADD COLUMN metadata_payload JSON")
            connection.exec_driver_sql(
                "UPDATE trained_model SET metadata_payload='{}' WHERE metadata_payload IS NULL"
            )
    set_user_version(engine, 5)


def apply_v6(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, 6)


def apply_v7(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        ml_task_info = connection.exec_driver_sql("PRAGMA table_info(ml_task)").all()
        trained_model_info = connection.exec_driver_sql("PRAGMA table_info(trained_model)").all()
    ml_task_work_item = next((row for row in ml_task_info if str(row[1]) == "work_item_id"), None)
    trained_model_work_item = next((row for row in trained_model_info if str(row[1]) == "work_item_id"), None)
    trained_model_columns = {str(row[1]) for row in trained_model_info}
    needs_rebuild = (
        ml_task_work_item is not None
        and int(ml_task_work_item[3]) == 1
        or trained_model_work_item is not None
        and int(trained_model_work_item[3]) == 1
        or "dataset_id" not in trained_model_columns
    )
    if not needs_rebuild:
        set_user_version(engine, 7)
        return

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("BEGIN")
        try:
            connection.exec_driver_sql(
                """
                CREATE TABLE ml_task_v7 (
                    id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    work_item_id TEXT,
                    dataset_id TEXT,
                    task_type VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    request_payload JSON NOT NULL,
                    result_payload JSON,
                    error_summary TEXT,
                    created_at DATETIME NOT NULL,
                    started_at DATETIME,
                    finished_at DATETIME,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(project_id) REFERENCES project (id),
                    FOREIGN KEY(work_item_id) REFERENCES work_item (id),
                    FOREIGN KEY(dataset_id) REFERENCES dataset (id)
                )
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO ml_task_v7 (
                    id, project_id, work_item_id, dataset_id, task_type, status,
                    request_payload, result_payload, error_summary,
                    created_at, started_at, finished_at, updated_at
                )
                SELECT
                    id, project_id, work_item_id, dataset_id, task_type, status,
                    request_payload, result_payload, error_summary,
                    created_at, started_at, finished_at, updated_at
                FROM ml_task
                """
            )
            connection.exec_driver_sql("DROP TABLE ml_task")
            connection.exec_driver_sql("ALTER TABLE ml_task_v7 RENAME TO ml_task")
            connection.exec_driver_sql(
                """
                CREATE TABLE trained_model_v7 (
                    id TEXT NOT NULL,
                    work_item_id TEXT,
                    dataset_id TEXT,
                    ml_task_id TEXT NOT NULL,
                    model_key TEXT NOT NULL,
                    problem_kind VARCHAR NOT NULL,
                    artifact_path TEXT NOT NULL,
                    metadata_payload JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(work_item_id) REFERENCES work_item (id),
                    FOREIGN KEY(dataset_id) REFERENCES dataset (id),
                    FOREIGN KEY(ml_task_id) REFERENCES ml_task (id),
                    UNIQUE (ml_task_id)
                )
                """
            )
            dataset_expr = "dataset_id" if "dataset_id" in trained_model_columns else "NULL"
            connection.exec_driver_sql(
                f"""
                INSERT INTO trained_model_v7 (
                    id, work_item_id, dataset_id, ml_task_id, model_key, problem_kind,
                    artifact_path, metadata_payload, created_at, updated_at
                )
                SELECT
                    id, work_item_id, {dataset_expr}, ml_task_id, model_key, problem_kind,
                    artifact_path, COALESCE(metadata_payload, '{{}}'), created_at, updated_at
                FROM trained_model
                """
            )
            connection.exec_driver_sql("DROP TABLE trained_model")
            connection.exec_driver_sql("ALTER TABLE trained_model_v7 RENAME TO trained_model")
            connection.exec_driver_sql("COMMIT")
        except Exception:
            connection.exec_driver_sql("ROLLBACK")
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    set_user_version(engine, 7)
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, 7)


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        apply_v5(engine)
        current_version = 5
    if current_version == 4:
        apply_v5(engine)
        current_version = 5
    if current_version == 5:
        apply_v6(engine)
        current_version = 6
    if current_version == 6:
        apply_v7(engine)
        return CURRENT_SCHEMA_VERSION
    if current_version < CURRENT_SCHEMA_VERSION:
        raise ValidationError(
            f"Local schema version {current_version} is no longer supported for automatic migration. "
            "Delete the local database and restart the app to bootstrap schema v6."
        )
    return current_version
