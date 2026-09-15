from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine


def create_engine_for_path(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # SQLite binds a connection to the thread that opened it; sessions cross
    # UI/worker/SSH threads here, so opt out of the same-thread check. This is a
    # threading guard, not a safety control.
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        # SQLite enforces foreign keys per-connection and only when enabled; enable
        # on every connect or the schema's FKs silently no-op.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
