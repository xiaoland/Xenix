from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from ...config import AppPaths
from ...exceptions import StorageBootstrapError
from .database import create_engine_for_path, create_session_factory
from .layout import database_path, ensure_storage_layout
from .migrations import run_migrations


@dataclass(frozen=True)
class StorageContext:
    """Storage runtime returned by StorageBootstrapService.initialize.

    schema_version is the post-migration applied version; engine and
    session_factory are caller-owned after a successful initialize.
    """

    paths: AppPaths
    engine: Engine
    session_factory: sessionmaker
    schema_version: int


class StorageBootstrapService:
    def initialize(self, paths: AppPaths) -> StorageContext:
        """Create the storage runtime for the given app paths.

        Creates the on-disk layout, opens (and owns) the SQLite engine, runs
        pending schema migrations, and returns a StorageContext whose
        schema_version is the resulting applied version. On failure the engine is
        disposed and StorageBootstrapError is raised.
        """
        engine: Engine | None = None
        try:
            ensure_storage_layout(paths)
            engine = create_engine_for_path(database_path(paths))
            schema_version = run_migrations(engine)
            session_factory = create_session_factory(engine)
        except Exception as exc:  # pragma: no cover - exercised through failure surface
            if engine is not None:
                engine.dispose()
            raise StorageBootstrapError("Unable to initialize local storage.") from exc

        return StorageContext(
            paths=paths,
            engine=engine,
            session_factory=session_factory,
            schema_version=schema_version,
        )
