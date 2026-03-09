from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from . import models  # noqa: F401

CURRENT_SCHEMA_VERSION = 1


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def set_user_version(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={version}")


def apply_v1(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, CURRENT_SCHEMA_VERSION)


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        apply_v1(engine)
        return CURRENT_SCHEMA_VERSION
    return current_version
