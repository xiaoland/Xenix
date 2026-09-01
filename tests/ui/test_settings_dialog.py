from __future__ import annotations

import threading
import time
from concurrent.futures import Future
from pathlib import Path

from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import TranslationManager
from xenix.services.embedding_service import EmbeddingSettingsService
from xenix.services.knowledge_index_service import KnowledgeIndexOverview
from xenix.services.llm import LLMService, LLMSettingsService
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.ui.settings_dialog import SettingsDialog


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
    qapp: QApplication,
    monkeypatch,
    tmp_path: Path,
    index_service,
    ssh_worker_setup: bool = True,
) -> SettingsDialog:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings = LLMSettingsService(paths)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        TranslationManager(qapp, paths),
        LLMService(llm_settings),
        llm_settings,
        MLWorkerSettingsService(paths),
        EmbeddingSettingsService(paths),
        knowledge_index_service=index_service,
        ssh_worker_setup=ssh_worker_setup,
    )
    return dialog


def test_settings_controls_have_stable_unique_semantic_identities(
    monkeypatch,
    tmp_path: Path,
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    dialog = _build_dialog(
        qapp=qapp,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=None,
    )
    qtbot.addWidget(dialog)
    controls = (
        dialog._language_selector,
        dialog._about_button,
        dialog._save_button,
        dialog._ocr_settings._setup_button,
        dialog._index_status._rebuild_button,
        dialog._ml_workers._setup_button,
        dialog._provider_editor._provider_selector,
        dialog._provider_editor._add_provider_button,
        dialog._provider_editor._remove_provider_button,
        dialog._provider_editor._provider_api_key_input,
        dialog._embedding_settings._api_key_input,
    )

    identities = [control.accessibleIdentifier() for control in controls]

    assert all(identities)
    assert len(identities) == len(set(identities))
    dialog.close()
    dialog.shutdown()


def test_settings_dialog_opens_before_index_status_finishes(
    monkeypatch,
    tmp_path: Path,
    qapp: QApplication,
    qtbot: QtBot,
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
    dialog = _build_dialog(
        qapp=qapp,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=indexes,
    )
    qtbot.addWidget(dialog)
    try:
        assert indexes.calls == 0

        dialog.show()

        qtbot.waitUntil(indexes.entered.is_set, timeout=3_000)
        assert dialog.isVisible()
        assert indexes.calls == 1
        assert indexes.thread_id != main_thread_id
        assert dialog._index_status._status_label.text() == dialog.tr(
            "Checking Knowledge index status"
        )
        assert not dialog._index_status._rebuild_button.isEnabled()

        indexes.release.set()
        qtbot.waitUntil(dialog._index_status._rebuild_button.isEnabled, timeout=3_000)
        assert dialog.tr("Ready") in dialog._index_status._status_label.text()
    finally:
        indexes.release.set()
        dialog.close()
        dialog.shutdown()


def test_settings_dialog_discards_status_from_previous_activation(
    monkeypatch,
    tmp_path: Path,
    qapp: QApplication,
    qtbot: QtBot,
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
    dialog = _build_dialog(
        qapp=qapp,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=indexes,
    )
    qtbot.addWidget(dialog)
    try:
        dialog.show()
        qtbot.waitUntil(indexes.entered[0].is_set, timeout=3_000)

        dialog.hide()
        qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=3_000)
        dialog.show()
        qtbot.waitUntil(dialog.isVisible, timeout=3_000)
        assert indexes.calls == 1

        indexes.release[0].set()
        qtbot.waitUntil(indexes.entered[1].is_set, timeout=3_000)
        assert dialog.tr("Needs attention") not in dialog._index_status._status_label.text()
        assert not dialog._index_status._rebuild_button.isEnabled()

        indexes.release[1].set()
        qtbot.waitUntil(dialog._index_status._rebuild_button.isEnabled, timeout=3_000)
        assert indexes.calls == 2
        assert indexes.max_in_flight == 1
        assert dialog.tr("Ready") in dialog._index_status._status_label.text()
    finally:
        for release in indexes.release:
            release.set()
        dialog.close()
        dialog.shutdown()


def test_settings_dialog_shutdown_does_not_wait_for_running_index_status(
    monkeypatch,
    tmp_path: Path,
    qapp: QApplication,
    qtbot: QtBot,
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
    dialog = _build_dialog(
        qapp=qapp,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=indexes,
    )
    qtbot.addWidget(dialog)
    fallback = threading.Timer(
        1.0,
        indexes.future.set_result,
        args=(_overview("ready", unit_count=67),),
    )
    fallback.daemon = True
    try:
        dialog.show()
        qtbot.waitUntil(lambda: indexes.calls == 1, timeout=3_000)

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


def test_ssh_worker_setup_is_denied_in_agent_safe_profile(
    monkeypatch,
    tmp_path: Path,
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    dialog = _build_dialog(
        qapp=qapp,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        index_service=None,
        ssh_worker_setup=False,
    )
    qtbot.addWidget(dialog)
    try:
        assert not dialog._ml_workers._setup_button.isEnabled()
        assert dialog._ml_workers._wizard is None

        dialog._ml_workers._open_ssh_worker_wizard()

        assert dialog._ml_workers._wizard is None
    finally:
        dialog.close()
        dialog.shutdown()
