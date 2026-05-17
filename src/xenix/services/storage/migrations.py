from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ...exceptions import ValidationError
from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 1


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


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        return bootstrap_current_schema(engine)
    if current_version == CURRENT_SCHEMA_VERSION:
        return current_version
    raise ValidationError(
        f"Local schema version {current_version} belongs to an obsolete development baseline. "
        f"Delete the local database and restart the app to bootstrap schema v{CURRENT_SCHEMA_VERSION}."
    )
