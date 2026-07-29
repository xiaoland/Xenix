from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import TranslationManager
from xenix.services.embedding_service import EmbeddingSettingsService
from xenix.services.knowledge_index_service import KnowledgeIndexOverview
from xenix.services.llm import LLMService, LLMSettingsService
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.services.settings_store import SettingsStore
from xenix.ui.settings_dialog import SettingsDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _wait_until(
    app: QApplication,
    condition: Callable[[], bool],
    *,
    timeout_seconds: float = 3.0,
) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.001)
    app.processEvents()
    return condition()


def _overview(state: str, *, unit_count: int) -> KnowledgeIndexOverview:
    return KnowledgeIndexOverview(
        keyword_state=state,
        text_vector_state=state,
        vector_configured=True,
        unit_count=unit_count,
        estimated_vector_requests=1,
        active_task_id=None,
        active_task_status=None,
        error_code=None,
    )


def _build_dialog(
    *,
    app: QApplication,
    monkeypatch,
    tmp_path: Path,
    index_service,
) -> tuple[SettingsDialog, SettingsStore]:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    settings_store = SettingsStore(paths.config)
    llm_settings = LLMSettingsService(settings_store=settings_store)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        TranslationManager(app, paths),
        LLMService(llm_settings),
        llm_settings,
        MLWorkerSettingsService(paths),
        EmbeddingSettingsService(settings_store=settings_store),
        knowledge_index_service=index_service,
    )
    return dialog, settings_store


def test_settings_dialog_opens_before_index_status_finishes(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    class BlockingIndexes:
        def __init__(self) -> None:
            self.entered = threading.Event()
            self.release = threading.Event()
            self.calls = 0
            self.thread_id: int | None = None

        def request_status(self) -> Future[KnowledgeIndexOverview]:
            future: Future[KnowledgeIndexOverview] = Future()
            self.calls += 1

            def complete() -> None:
                if not future.set_running_or_notify_cancel():
                    return
                self.thread_id = threading.get_ident()
                self.entered.set()
                if not self.release.wait(timeout=3):
                    future.set_exception(
                        TimeoutError("Index status test release timed out.")
                    )
                    return
                future.set_result(_overview("ready", unit_count=67))

            threading.Thread(target=complete, daemon=True).start()
            return future

    indexes = BlockingIndexes()
    main_thread_id = threading.get_ident()
    dialog, settings_store = _build_dialog(
        app=app,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=indexes,
    )
    try:
        assert indexes.calls == 0

        dialog.show()

        assert _wait_until(app, indexes.entered.is_set)
        assert dialog.isVisible()
        assert indexes.calls == 1
        assert indexes.thread_id != main_thread_id
        assert dialog._index_status_label.text() == dialog.tr(
            "Checking Knowledge index status"
        )
        assert not dialog._index_rebuild_button.isEnabled()

        indexes.release.set()
        assert _wait_until(app, dialog._index_rebuild_button.isEnabled)
        assert dialog.tr("Ready") in dialog._index_status_label.text()
    finally:
        indexes.release.set()
        dialog.close()
        dialog.shutdown()
        settings_store.close()


def test_settings_dialog_discards_status_from_previous_activation(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    class SequencedIndexes:
        def __init__(self) -> None:
            self.entered = (threading.Event(), threading.Event())
            self.release = (threading.Event(), threading.Event())
            self._lock = threading.Lock()
            self.calls = 0
            self.in_flight = 0
            self.max_in_flight = 0

        def request_status(self) -> Future[KnowledgeIndexOverview]:
            future: Future[KnowledgeIndexOverview] = Future()
            with self._lock:
                call_index = self.calls
                self.calls += 1

            def complete() -> None:
                if not future.set_running_or_notify_cancel():
                    return
                with self._lock:
                    self.in_flight += 1
                    self.max_in_flight = max(self.max_in_flight, self.in_flight)
                self.entered[call_index].set()
                if not self.release[call_index].wait(timeout=3):
                    future.set_exception(
                        TimeoutError("Index status test release timed out.")
                    )
                    return
                try:
                    if call_index == 0:
                        result = _overview("needs_attention", unit_count=0)
                    else:
                        result = _overview("ready", unit_count=67)
                    future.set_result(result)
                finally:
                    with self._lock:
                        self.in_flight -= 1

            threading.Thread(target=complete, daemon=True).start()
            return future

    indexes = SequencedIndexes()
    dialog, settings_store = _build_dialog(
        app=app,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=indexes,
    )
    try:
        dialog.show()
        assert _wait_until(app, indexes.entered[0].is_set)

        dialog.hide()
        app.processEvents()
        dialog.show()
        app.processEvents()
        assert indexes.calls == 1

        indexes.release[0].set()
        assert _wait_until(app, indexes.entered[1].is_set)
        assert dialog.tr("Needs attention") not in dialog._index_status_label.text()
        assert not dialog._index_rebuild_button.isEnabled()

        indexes.release[1].set()
        assert _wait_until(app, dialog._index_rebuild_button.isEnabled)
        assert indexes.calls == 2
        assert indexes.max_in_flight == 1
        assert dialog.tr("Ready") in dialog._index_status_label.text()
    finally:
        for release in indexes.release:
            release.set()
        dialog.close()
        dialog.shutdown()
        settings_store.close()


def test_settings_dialog_shutdown_does_not_wait_for_running_index_status(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    class ObservedFuture(Future[KnowledgeIndexOverview]):
        def __init__(self) -> None:
            super().__init__()
            self.cancel_calls = 0

        def cancel(self) -> bool:
            self.cancel_calls += 1
            return super().cancel()

    class RunningIndexes:
        def __init__(self) -> None:
            self.future = ObservedFuture()
            assert self.future.set_running_or_notify_cancel()
            self.calls = 0

        def request_status(self) -> Future[KnowledgeIndexOverview]:
            self.calls += 1
            return self.future

    indexes = RunningIndexes()
    dialog, settings_store = _build_dialog(
        app=app,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=indexes,
    )
    fallback = threading.Timer(
        1.0,
        indexes.future.set_result,
        args=(_overview("ready", unit_count=67),),
    )
    fallback.daemon = True
    try:
        dialog.show()
        assert _wait_until(app, lambda: indexes.calls == 1)

        started = time.perf_counter()
        dialog.shutdown()
        elapsed = time.perf_counter() - started

        assert elapsed < 0.25
        assert indexes.future.cancel_calls == 1
        assert not indexes.future.done()
    finally:
        fallback.cancel()
        if not indexes.future.done():
            indexes.future.set_result(_overview("ready", unit_count=67))
        dialog.close()
        dialog.shutdown()
        settings_store.close()
