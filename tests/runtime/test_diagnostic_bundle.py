from __future__ import annotations

import importlib.util
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from types import ModuleType

import pytest

from xenix.config import AppPaths, ensure_app_dirs, get_app_paths
from xenix.services.storage.layout import database_path, knowledge_import_logs_path, task_logs_path

from tests.support.paths import project_script


@pytest.fixture
def bundle_script() -> ModuleType:
    script_path = project_script("create_diagnostic_bundle.py")
    spec = importlib.util.spec_from_file_location("create_diagnostic_bundle", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_diagnostic_bundle_contains_logs_and_metadata_without_raw_database(
    bundle_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SQLite URI construction must preserve spaces and URI delimiters in the home path.
    home = tmp_path / "xenix home #1"
    monkeypatch.setenv("XENIX_APP_HOME", str(home))
    app_paths = ensure_app_dirs(get_app_paths())
    logs = {
        app_paths.logs / "xenix.log": b'{"event":"hello"}\n',
        app_paths.logs / "xenix.log.1": b'{"event":"rotated"}\n',
        app_paths.logs / "xenix.log.3": b'{"event":"older"}\n',
        task_logs_path(app_paths, 1): b'{"level":"INFO","message":"task"}\n',
        knowledge_import_logs_path(app_paths, 2): b'{"phase":"queued","event_code":"created"}\n',
    }
    for path, data in logs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (app_paths.logs / "xenix.log.old").write_text("unrelated", encoding="utf-8")
    with closing(sqlite3.connect(database_path(app_paths))) as connection:
        connection.execute("PRAGMA user_version=13")
        connection.execute("CREATE TABLE sample (id TEXT)")
        connection.execute("INSERT INTO sample (id) VALUES ('row-1')")
        connection.commit()

    output_path = tmp_path / "bundle.zip"
    assert bundle_script.main(["--output", str(output_path)]) == 0

    with zipfile.ZipFile(output_path) as bundle:
        expected_logs = {path.relative_to(home).as_posix(): data for path, data in logs.items()}
        assert set(bundle.namelist()) == {"metadata.json", "config/telemetry.json", *expected_logs}
        assert {name: bundle.read(name) for name in expected_logs} == expected_logs
        metadata = json.loads(bundle.read("metadata.json"))

    assert metadata["runtime_home_class"] == "custom"
    assert metadata["install_id"] == json.loads((app_paths.config / "telemetry.json").read_bytes())["install_id"]
    assert metadata["sqlite"] == {"exists": True, "user_version": 13, "table_counts": {"sample": 1}}
    assert metadata["logs"]["omitted"] == []


def test_diagnostic_bundle_with_missing_database(bundle_script: ModuleType, app_paths: AppPaths, tmp_path: Path) -> None:
    output_path = tmp_path / "bundle.zip"
    assert bundle_script.main(["--output", str(output_path)]) == 0

    with zipfile.ZipFile(output_path) as bundle:
        assert json.loads(bundle.read("metadata.json"))["sqlite"] == {"exists": False}
    assert not database_path(app_paths).exists()


def test_diagnostic_bundle_with_corrupt_database(bundle_script: ModuleType, app_paths: AppPaths, tmp_path: Path) -> None:
    invalid_data = b"invalid database with private content"
    db_path = database_path(app_paths)
    db_path.write_bytes(invalid_data)
    (app_paths.logs / "xenix.log").write_bytes(b'{"event":"still readable"}\n')

    output_path = tmp_path / "bundle.zip"
    assert bundle_script.main(["--output", str(output_path)]) == 0

    with zipfile.ZipFile(output_path) as bundle:
        assert bundle.read("logs/xenix.log") == b'{"event":"still readable"}\n'
        assert "state/xenix.db" not in bundle.namelist()
        assert json.loads(bundle.read("metadata.json"))["sqlite"] == {
            "exists": True,
            "status": "unavailable",
            "error": {"category": "SQLITE_NOTADB", "message": "SQLite database summary could not be read."},
        }
    assert db_path.read_bytes() == invalid_data


def test_diagnostic_bundle_with_locked_database(bundle_script: ModuleType, app_paths: AppPaths, tmp_path: Path) -> None:
    output_path = tmp_path / "bundle.zip"
    with closing(sqlite3.connect(database_path(app_paths))) as connection:
        connection.execute("BEGIN EXCLUSIVE")
        assert bundle_script.main(["--output", str(output_path)]) == 0

    with zipfile.ZipFile(output_path) as bundle:
        summary = json.loads(bundle.read("metadata.json"))["sqlite"]
    assert summary["status"] == "unavailable"
    assert summary["error"]["category"] == "SQLITE_BUSY"


def test_diagnostic_bundle_lists_logs_omitted_by_size_limits(
    bundle_script: ModuleType, app_paths: AppPaths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle_script, "MAX_LOG_FILE_BYTES", 8)
    monkeypatch.setattr(bundle_script, "MAX_TOTAL_LOG_BYTES", 12)
    (app_paths.logs / "xenix.log").write_bytes(b"now\n")
    (app_paths.logs / "xenix.log.1").write_bytes(b"past\n")
    (app_paths.logs / "xenix.log.2").write_bytes(b"oversized\n")
    (app_paths.logs / "xenix.log.3").write_bytes(b"old!\n")
    ml_log = task_logs_path(app_paths, 1)
    ml_log.parent.mkdir(parents=True)
    ml_log.write_bytes(b"ml\n")

    output_path = tmp_path / "bundle.zip"
    assert bundle_script.main(["--output", str(output_path)]) == 0

    with zipfile.ZipFile(output_path) as bundle:
        assert bundle.read("logs/xenix.log") == b"now\n"
        assert bundle.read("logs/xenix.log.1") == b"past\n"
        assert bundle.read("artifacts/ml-tasks/1/logs.jsonl") == b"ml\n"
        assert "logs/xenix.log.2" not in bundle.namelist()
        assert "logs/xenix.log.3" not in bundle.namelist()
        assert json.loads(bundle.read("metadata.json"))["logs"] == {
            "max_file_bytes": 8,
            "max_total_bytes": 12,
            "included_bytes": 12,
            "omitted": [
                {"path": "logs/xenix.log.2", "reason": "file_limit"},
                {"path": "logs/xenix.log.3", "reason": "total_limit"},
            ],
        }
