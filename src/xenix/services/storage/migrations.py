from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 4


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def set_user_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={version}")


def bootstrap_current_schema(engine: Engine) -> int:
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, CURRENT_SCHEMA_VERSION)
    return CURRENT_SCHEMA_VERSION


def migrate_v1_to_v2(engine: Engine) -> int:
    with engine.begin() as connection:
        dataset_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(dataset)").all()
        }
        if "derived_from_dataset_id" not in dataset_columns:
            connection.exec_driver_sql(
                "ALTER TABLE dataset ADD COLUMN derived_from_dataset_id VARCHAR"
            )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dataset_derived_from_dataset_id "
            "ON dataset (derived_from_dataset_id)"
        )
        connection.exec_driver_sql("PRAGMA user_version=2")
    return 2


def migrate_v2_to_v3(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "agent_message" not in table_names:
            connection.exec_driver_sql("PRAGMA user_version=3")
            return 3
        agent_message_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_message)").all()
        }
        if "status" not in agent_message_columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_message ADD COLUMN status VARCHAR"
            )
            connection.exec_driver_sql(
                "UPDATE agent_message SET status='completed' WHERE status IS NULL"
            )
        if "updated_at" not in agent_message_columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_message ADD COLUMN updated_at DATETIME"
            )
            connection.exec_driver_sql(
                "UPDATE agent_message SET updated_at=created_at WHERE updated_at IS NULL"
            )
        if "finalized_at" not in agent_message_columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_message ADD COLUMN finalized_at DATETIME"
            )
            connection.exec_driver_sql(
                "UPDATE agent_message SET finalized_at=created_at WHERE finalized_at IS NULL"
            )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_agent_message_status "
            "ON agent_message (status)"
        )
        connection.exec_driver_sql("PRAGMA user_version=3")
    return 3


def migrate_v3_to_v4(engine: Engine) -> int:
    with engine.begin() as connection:
        table_names = {
            str(row[0])
            for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
        }
        if "agent_message" not in table_names:
            connection.exec_driver_sql("PRAGMA user_version=4")
            return 4
        agent_message_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(agent_message)").all()
        }
        if "status" in agent_message_columns:
            status_pairs = {
                "IN_PROGRESS": "in_progress",
                "COMPLETED": "completed",
                "FAILED": "failed",
                "CANCELLED": "cancelled",
            }
            for old_value, new_value in status_pairs.items():
                connection.exec_driver_sql(
                    "UPDATE agent_message SET status=? WHERE status=?",
                    (new_value, old_value),
                )
        connection.exec_driver_sql("PRAGMA user_version=4")
    return 4


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        return bootstrap_current_schema(engine)
    if current_version == 1:
        current_version = migrate_v1_to_v2(engine)
    if current_version == 2:
        current_version = migrate_v2_to_v3(engine)
    if current_version == 3:
        current_version = migrate_v3_to_v4(engine)
    if current_version == CURRENT_SCHEMA_VERSION:
        return current_version
    raise ValidationError(
        f"Local schema version {current_version} belongs to an obsolete development baseline. "
        f"Delete the local database and restart the app to bootstrap schema v{CURRENT_SCHEMA_VERSION}."
    )
