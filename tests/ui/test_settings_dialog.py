from __future__ import annotations

import threading
import time
from concurrent.futures import Future
from pathlib import Path

from PySide6.QtCore import QEvent
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
            self.requests: list[Future[KnowledgeIndexOverview]] = []

        def request_status(self) -> Future[KnowledgeIndexOverview]:
            future: Future[KnowledgeIndexOverview] = Future()
            self.requests.append(future)
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
        qtbot.waitUntil(lambda: len(indexes.requests) == 1, timeout=3_000)
        stale_request = indexes.requests[0]
        assert stale_request.set_running_or_notify_cancel()

        dialog.hide()
        dialog.show()
        qtbot.waitUntil(lambda: len(indexes.requests) == 2, timeout=3_000)
        fresh_request = indexes.requests[1]
        assert stale_request.running()

        # The service runs reads one at a time. Deliver the obsolete result
        # while the next request is still pending and flush its queued signal.
        stale_request.set_result(_overview("needs_attention", unit_count=0))
        QApplication.sendPostedEvents(dialog._index_status, QEvent.Type.MetaCall)
        assert dialog.tr("Needs attention") not in dialog._index_status._status_label.text()
        assert not dialog._index_status._rebuild_button.isEnabled()

        assert fresh_request.set_running_or_notify_cancel()
        fresh_request.set_result(_overview("ready", unit_count=67))
        qtbot.waitUntil(dialog._index_status._rebuild_button.isEnabled, timeout=3_000)
        assert len(indexes.requests) == 2
        assert dialog.tr("Ready") in dialog._index_status._status_label.text()
    finally:
        dialog.close()
        dialog.shutdown()
        for request in indexes.requests:
            if request.running():
                request.set_result(_overview("ready", unit_count=67))


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
