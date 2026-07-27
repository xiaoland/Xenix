from __future__ import annotations

import hashlib
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pikepdf
import psutil
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.artifact_service import ArtifactService
from xenix.services.knowledge_derivation_service import KnowledgeDerivationService
from xenix.services.knowledge_import_service import KnowledgeImportService
from xenix.services.knowledge_import_worker import (
    KnowledgeImportWorkerEvent,
    LocalKnowledgeImportWorkerRunner,
    read_worker_result,
)
from xenix.services.knowledge_service import KnowledgeService
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


def _uncancellable_worker_tree_entry(_request, _cancel_event, event_queue) -> None:
    grandchild = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
    )
    event_queue.put(
        KnowledgeImportWorkerEvent(
            "parsing",
            f"grandchild-{grandchild.pid}",
        )
    )
    while True:
        time.sleep(0.05)


def _timed_out_worker_entry(_request, _cancel_event, _event_queue) -> None:
    while True:
        time.sleep(0.05)


def _invalid_result_worker_entry(request, _cancel_event, _event_queue) -> None:
    knowledge_import_result_path(request.paths, request.import_id).write_text(
        "invalid worker result",
        encoding="utf-8",
    )


class _EmptyEventQueue:
    def get_nowait(self):
        raise queue.Empty

    def close(self) -> None:
        pass

    def join_thread(self) -> None:
        pass


class _LaunchFailingProcess:
    def start(self) -> None:
        raise OSError("simulated process launch failure")

    def is_alive(self) -> bool:
        return False


class _LaunchFailingContext:
    def Event(self):
        return threading.Event()

    def Queue(self):
        return _EmptyEventQueue()

    def Process(self, **_kwargs):
        return _LaunchFailingProcess()


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


def test_spawned_worker_failure_stage_and_diagnostic_are_content_free(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, storage, importer = _runtime(monkeypatch, tmp_path)
    source = tmp_path / "private-customer-plan.pdf"
    private_content = "客户甲的未公开渠道策略"
    with pikepdf.new() as document:
        document.add_blank_page()
        document.docinfo["/Subject"] = private_content
        document.save(
            source,
            encryption=pikepdf.Encryption(
                owner="owner-password",
                user="transient-password",
            ),
        )

    try:
        with pytest.raises(ValidationError) as error:
            importer.import_file(source, timeout=30)
        failed = importer.list_imports()[0]
        worker_result = read_worker_result(
            knowledge_import_result_path(paths, failed.import_id)
        )
        raw_log = knowledge_import_logs_path(paths, failed.import_id).read_text(
            encoding="utf-8"
        )

        assert error.value.error_code == "knowledge_password_required"
        assert worker_result.failure_stage == "normalizing"
        assert worker_result.diagnostic_code == "validation_error"
        assert "normalizing_failed" in raw_log
        assert "validation_error" in raw_log
        assert source.name not in raw_log
        assert str(source.resolve()) not in raw_log
        assert private_content not in raw_log
        assert "transient-password" not in raw_log
    finally:
        importer.shutdown()
        storage.engine.dispose()


def test_spawned_import_worker_parses_the_named_large_pptx_and_reaches_lookup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = (
        Path(__file__).parent
        / ".mock-data"
        / "2026半年度工作汇报（品牌营销）.pptx"
    )
    if not source.is_file():
        pytest.skip("named Knowledge PPTX acceptance fixture is unavailable")
    assert source.stat().st_size == 53_093_313
    with source.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == (
            "effa60d7951eac3b88e260c9e09e9e3e46d4a0b197650d8222950af92d89c939"
        )

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    derivation = KnowledgeDerivationService(
        paths=paths,
        session_factory=storage.session_factory,
        start_worker=False,
    )
    importer = KnowledgeImportService(
        paths=paths,
        session_factory=storage.session_factory,
        artifact_service=ArtifactService(storage.session_factory),
        canonical_ready_notifier=derivation.enqueue_generation,
    )
    knowledge = KnowledgeService(storage.session_factory)
    try:
        imported = importer.import_file(source, timeout=180)
        worker_result = read_worker_result(
            knowledge_import_result_path(paths, imported.import_id)
        )
        derivation_view = derivation.status_for_import(imported.import_id)
        assert derivation_view is not None
        derived = derivation.derive_now(derivation_view.job_id)
        matches = knowledge.lookup("菜单瘦身", top_k=5)

        assert worker_result.worker_pid != os.getpid()
        assert worker_result.status == "succeeded"
        assert worker_result.failure_stage is None
        assert worker_result.diagnostic_code is None
        assert derived.retrieval_ready is True
        assert matches
        assert any("菜单瘦身" in match.quote for match in matches)
    finally:
        importer.shutdown()
        derivation.shutdown()
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


def test_worker_launch_failure_is_retryable_and_distinct(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "xenix.services.knowledge_import_worker.get_context",
        lambda _method: _LaunchFailingContext(),
    )
    _paths, storage, importer = _runtime(monkeypatch, tmp_path)
    source = tmp_path / "rule.txt"
    source.write_text("启动失败任务不得发布文档", encoding="utf-8")

    try:
        with pytest.raises(ValidationError) as error:
            importer.import_file(source, timeout=30)
        view = importer.list_imports()[0]
        event_codes = {
            event.event_code for event in importer.read_import_logs(view.import_id)
        }

        assert error.value.error_code == "knowledge_import_worker_launch_failed"
        assert view.document_id is None
        assert view.retryable is True
        assert "worker_launch_failed" in event_codes
        assert "knowledge_import_worker_launch_failed" in event_codes
    finally:
        importer.shutdown()
        storage.engine.dispose()


def test_invalid_worker_result_is_reported_as_output_validation_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = LocalKnowledgeImportWorkerRunner(
        entrypoint=_invalid_result_worker_entry,
    )
    _paths, storage, importer = _runtime(
        monkeypatch,
        tmp_path,
        worker_runner=runner,
    )
    source = tmp_path / "rule.txt"
    source.write_text("无效结果不得发布文档", encoding="utf-8")

    try:
        with pytest.raises(ValidationError) as error:
            importer.import_file(source, timeout=30)
        view = importer.list_imports()[0]
        event_codes = {
            event.event_code for event in importer.read_import_logs(view.import_id)
        }

        assert error.value.error_code == "knowledge_import_worker_crashed"
        assert view.document_id is None
        assert view.retryable is True
        assert "worker_result_invalid" in event_codes
    finally:
        importer.shutdown()
        storage.engine.dispose()


def test_worker_timeout_is_retryable_and_persists_a_distinct_task_event(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = LocalKnowledgeImportWorkerRunner(
        entrypoint=_timed_out_worker_entry,
        operation_timeout=0.2,
        cancel_grace=0.1,
    )
    _paths, storage, importer = _runtime(
        monkeypatch,
        tmp_path,
        worker_runner=runner,
    )
    source = tmp_path / "rule.txt"
    source.write_text("超时任务不得发布文档", encoding="utf-8")

    try:
        with pytest.raises(ValidationError) as error:
            importer.import_file(source, timeout=30)
        view = importer.list_imports()[0]
        event_codes = {
            event.event_code for event in importer.read_import_logs(view.import_id)
        }

        assert error.value.error_code == "knowledge_import_worker_timed_out"
        assert view.document_id is None
        assert view.retryable is True
        assert "worker_operation_timed_out" in event_codes
        assert "knowledge_import_worker_timed_out" in event_codes
    finally:
        importer.shutdown()
        storage.engine.dispose()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object contract")
def test_worker_timeout_terminates_the_entire_worker_process_tree(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = LocalKnowledgeImportWorkerRunner(
        entrypoint=_uncancellable_worker_tree_entry,
        operation_timeout=20.0,
        cancel_grace=0.2,
    )
    _paths, storage, importer = _runtime(
        monkeypatch,
        tmp_path,
        worker_runner=runner,
    )
    source = tmp_path / "rule.txt"
    source.write_text("超时必须清理整个进程树", encoding="utf-8")
    grandchild_pid: int | None = None
    try:
        receipt = importer.enqueue_file(source)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and grandchild_pid is None:
            for event in importer.read_import_logs(receipt.import_id):
                if event.event_code.startswith("grandchild-"):
                    grandchild_pid = int(event.event_code.removeprefix("grandchild-"))
                    break
            time.sleep(0.02)
        assert grandchild_pid is not None and psutil.pid_exists(grandchild_pid)

        with pytest.raises(ValidationError) as error:
            importer.wait_for_import(receipt.import_id, timeout=30)
        assert error.value.error_code == "knowledge_import_worker_timed_out"

        deadline = time.monotonic() + 5
        while psutil.pid_exists(grandchild_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not psutil.pid_exists(grandchild_pid)
    finally:
        if grandchild_pid is not None and psutil.pid_exists(grandchild_pid):
            psutil.Process(grandchild_pid).kill()
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object contract")
def test_forced_import_cancellation_terminates_the_entire_worker_process_tree(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = LocalKnowledgeImportWorkerRunner(
        entrypoint=_uncancellable_worker_tree_entry,
        cancel_grace=0.2,
    )
    _paths, storage, importer = _runtime(
        monkeypatch,
        tmp_path,
        worker_runner=runner,
    )
    source = tmp_path / "rule.txt"
    source.write_text("强制取消进程树", encoding="utf-8")
    grandchild_pid: int | None = None
    try:
        receipt = importer.enqueue_file(source)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and grandchild_pid is None:
            for event in importer.read_import_logs(receipt.import_id):
                if event.event_code.startswith("grandchild-"):
                    grandchild_pid = int(event.event_code.removeprefix("grandchild-"))
                    break
            time.sleep(0.02)
        assert grandchild_pid is not None and psutil.pid_exists(grandchild_pid)

        assert importer.cancel_import(receipt.import_id) is True
        with pytest.raises(ValidationError) as error:
            importer.wait_for_import(receipt.import_id, timeout=30)
        assert error.value.error_code == "knowledge_import_cancelled"

        deadline = time.monotonic() + 5
        while psutil.pid_exists(grandchild_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not psutil.pid_exists(grandchild_pid)
    finally:
        if grandchild_pid is not None and psutil.pid_exists(grandchild_pid):
            psutil.Process(grandchild_pid).kill()
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
