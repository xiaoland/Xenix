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
        trained_model_columns = {
            str(row[1])
            for row in connection.exec_driver_sql("PRAGMA table_info(trained_model)").all()
        }

    assert CURRENT_SCHEMA_VERSION == 1
    assert "work_item" not in table_names
    assert "work_item_id" not in ml_task_columns
    assert "work_item_id" not in trained_model_columns
