import sqlite3
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import StorageBootstrapError
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import database_path
from xenix.services.storage.migrations import CURRENT_SCHEMA_VERSION, get_user_version


def _create_legacy_database(db_path: Path, version: int) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(f"PRAGMA user_version={version}")
        connection.commit()
    finally:
        connection.close()


def test_storage_bootstrap_rejects_legacy_local_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    _create_legacy_database(database_path(paths), 99)

    with pytest.raises(StorageBootstrapError):
        StorageBootstrapService().initialize(paths)


def test_storage_bootstrap_bootstraps_fresh_v1_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())

    context = StorageBootstrapService().initialize(paths)

    assert get_user_version(context.engine) == CURRENT_SCHEMA_VERSION
