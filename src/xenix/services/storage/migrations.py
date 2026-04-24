from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 5


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
    set_user_version(engine, CURRENT_SCHEMA_VERSION)


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        apply_v5(engine)
        return CURRENT_SCHEMA_VERSION
    if current_version == 4:
        apply_v5(engine)
        return CURRENT_SCHEMA_VERSION
    if current_version < CURRENT_SCHEMA_VERSION:
        raise ValidationError(
            f"Local schema version {current_version} is no longer supported for automatic migration. "
            "Delete the local database and restart the app to bootstrap schema v5."
        )
    return current_version
