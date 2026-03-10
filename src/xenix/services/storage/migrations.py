from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 2


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def set_user_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={version}")


def apply_v2(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, CURRENT_SCHEMA_VERSION)


def apply_v1_to_v2(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
            """
            CREATE TABLE work_item_v2 (
                id TEXT NOT NULL PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                dataset_id TEXT,
                feature_columns JSON NOT NULL,
                target_columns JSON NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY(project_id) REFERENCES project (id),
                FOREIGN KEY(dataset_id) REFERENCES dataset (id)
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO work_item_v2 (
                id,
                project_id,
                name,
                description,
                dataset_id,
                feature_columns,
                target_columns,
                created_at,
                updated_at
            )
            SELECT
                id,
                project_id,
                name,
                description,
                NULL,
                '[]',
                '[]',
                created_at,
                updated_at
            FROM work_item
            """
        )
        connection.exec_driver_sql("DROP TABLE work_item")
        connection.exec_driver_sql("ALTER TABLE work_item_v2 RENAME TO work_item")
        connection.exec_driver_sql("CREATE INDEX ix_work_item_project_id ON work_item (project_id)")
        connection.exec_driver_sql("CREATE INDEX ix_work_item_name ON work_item (name)")
        connection.exec_driver_sql("CREATE INDEX ix_work_item_dataset_id ON work_item (dataset_id)")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    set_user_version(engine, CURRENT_SCHEMA_VERSION)


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        apply_v2(engine)
        return CURRENT_SCHEMA_VERSION
    if current_version == 1:
        apply_v1_to_v2(engine)
        return CURRENT_SCHEMA_VERSION
    return current_version
