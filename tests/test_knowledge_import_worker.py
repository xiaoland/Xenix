from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.artifact_service import ArtifactService
from xenix.services.knowledge_import_service import KnowledgeImportService
from xenix.services.knowledge_import_worker import (
    KnowledgeImportWorkerEvent,
    LocalKnowledgeImportWorkerRunner,
    read_worker_result,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.layout import (
    knowledge_import_logs_path,
    knowledge_import_result_path,
)


def _crashing_worker_entry(_request, _cancel_event, _event_queue) -> None:
    os._exit(23)


def _cancellable_worker_entry(_request, cancel_event, event_queue) -> None:
    event_queue.put(KnowledgeImportWorkerEvent("parsing", "worker_started"))
    while not cancel_event.wait(0.02):
        pass


def test_default_import_runner_executes_in_a_spawned_process(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, importer = _runtime(monkeypatch, tmp_path)
    source = tmp_path / "rule.txt"
    private_content = "雨季库存按三周需求补货。仅供内部使用。"
    source.write_text(private_content, encoding="utf-8")

    try:
        result = importer.import_file(source, timeout=60)
        worker_result = read_worker_result(
            knowledge_import_result_path(paths, result.import_id)
        )
        events = importer.read_import_logs(result.import_id)
        raw_log = knowledge_import_logs_path(paths, result.import_id).read_text(
            encoding="utf-8"
        )

        assert worker_result.worker_pid != os.getpid()
        assert worker_result.status == "succeeded"
        assert "worker_started" in {event.event_code for event in events}
        assert events[-1].event_code == "import_completed"
        assert source.name not in raw_log
        assert str(source) not in raw_log
        assert private_content not in raw_log
    finally:
        importer.shutdown()
        storage.engine.dispose()


def test_worker_crash_cannot_publish_a_document(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = LocalKnowledgeImportWorkerRunner(entrypoint=_crashing_worker_entry)
    _paths, storage, importer = _runtime(
        monkeypatch,
        tmp_path,
        worker_runner=runner,
    )
    source = tmp_path / "rule.txt"
    source.write_text("不应被发布的内容", encoding="utf-8")

    try:
        with pytest.raises(ValidationError) as error:
            importer.import_file(source, timeout=30)
        view = importer.list_imports()[0]

        assert error.value.error_code == "knowledge_import_worker_crashed"
        assert view.document_id is None
        assert view.retryable is True
        assert importer.read_import_logs(view.import_id)[-1].event_code == (
            "knowledge_import_worker_crashed"
        )
    finally:
        importer.shutdown()
        storage.engine.dispose()


def test_running_worker_is_cancelled_and_leaves_no_current_document(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = LocalKnowledgeImportWorkerRunner(
        entrypoint=_cancellable_worker_entry,
        cancel_grace=2,
    )
    _paths, storage, importer = _runtime(
        monkeypatch,
        tmp_path,
        worker_runner=runner,
    )
    source = tmp_path / "rule.txt"
    source.write_text("将被取消的内容", encoding="utf-8")

    try:
        receipt = importer.enqueue_file(source)
        _wait_for_event(importer, receipt.import_id, "worker_started")
        assert importer.cancel_import(receipt.import_id) is True
        with pytest.raises(ValidationError) as error:
            importer.wait_for_import(receipt.import_id, timeout=30)
        view = importer.list_imports()[0]

        assert error.value.error_code == "knowledge_import_cancelled"
        assert view.status == "cancelled"
        assert view.document_id is None
    finally:
        importer.shutdown()
        storage.engine.dispose()


def _runtime(monkeypatch, tmp_path: Path, *, worker_runner=None):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    importer = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        worker_runner=worker_runner,
    )
    return paths, storage, importer


def _wait_for_event(
    importer: KnowledgeImportService,
    import_id: str,
    event_code: str,
    *,
    timeout: float = 20,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if event_code in {
            event.event_code for event in importer.read_import_logs(import_id)
        }:
            return
        time.sleep(0.02)
    raise AssertionError(f"Knowledge import event was not observed: {event_code}")
