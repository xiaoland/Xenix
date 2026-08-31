"""Visible desktop adapter for the real-provider Agent Harness benchmark."""

from __future__ import annotations

import gc
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable

from PySide6.QtCore import QEvent, QEventLoop, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from xenix.application_services import ApplicationServices
from xenix.config import AppPaths
from xenix.services.storage.layout import database_path
from xenix.ui.knowledge_workspace import KnowledgeWorkspaceDialog
from xenix.services.embedding_service import EmbeddingSettings, EmbeddingSettingsService
from xenix.services.llm import LLMService, LLMSettings, LLMSettingsService

from .contracts import (
    BenchmarkCase,
    BenchmarkCasePreparationServices,
    BenchmarkCaseServices,
    OutcomeCheck,
)


_TERMINAL_TASK_STATUSES = frozenset(
    {"succeeded", "failed", "cancelled", "needs_attention", "reused"}
)
_SUBJECT_TURN_TIMEOUT_SECONDS = 900.0


class HeadedBenchmarkError(RuntimeError):
    """A privacy-safe visible-execution failure persisted by the shared runner."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _HeadedKnowledgeImportAccess:
    def __init__(self, cell: HeadedBenchmarkCell) -> None:
        self._cell = cell

    def import_file(self, source_path: Path, *, timeout: float = 60.0) -> Any:
        return self._cell.import_knowledge_file(source_path, timeout=timeout)


class _HeadedKnowledgeDerivationAccess:
    def __init__(self, cell: HeadedBenchmarkCell) -> None:
        self._cell = cell

    def status_for_import(self, import_id: str) -> Any:
        self._cell.pump_events()
        return self._cell.runtime_services.knowledge_derivation.status_for_import(  # noqa: SLF001
            import_id
        )


class _HeadedKnowledgeIndexAccess:
    def __init__(self, cell: HeadedBenchmarkCell) -> None:
        self._cell = cell

    def enqueue_rebuild(self, index_kinds: Any, *, trigger: str) -> str:
        task_id = self._cell.runtime_services.knowledge_index.enqueue_rebuild(  # noqa: SLF001
            index_kinds,
            trigger=trigger,
        )
        self._cell.knowledge_index_task_ids.add(task_id)
        return task_id

    def rebuild_now(self, task_id: str) -> Any:
        service = self._cell.runtime_services.knowledge_index  # noqa: SLF001

        def terminal_task() -> Any | None:
            task = next(
                (item for item in service.list_tasks() if item.task_id == task_id),
                None,
            )
            if task is not None and task.status in _TERMINAL_TASK_STATUSES:
                return task
            return None

        return self._cell.wait_for_value(
            terminal_task,
            timeout=900.0,
            error_code="headed_knowledge_index_timeout",
        )


class HeadedBenchmarkCell:
    """Drive one benchmark cell through real, visible Qt user surfaces."""

    def __init__(
        self,
        *,
        paths: AppPaths,
        settings: LLMSettings,
        embedding_settings: EmbeddingSettings | None,
        bounded_llm: LLMService,
    ) -> None:
        self.paths = paths
        self._previous_app_home = os.environ.get("XENIX_APP_HOME")
        self._closed = False
        self._checks: list[OutcomeCheck] = []
        self._knowledge_results: dict[str, Any] = {}
        self.knowledge_index_task_ids: set[str] = set()
        self.app: QApplication
        self.window: Any
        self.runtime_services: ApplicationServices

        LLMSettingsService(paths).save(settings)
        if embedding_settings is not None:
            EmbeddingSettingsService(paths).save(embedding_settings)
        os.environ["XENIX_APP_HOME"] = str(paths.home)
        try:
            from xenix.app import build_main_window

            self.app, self.window = build_main_window(
                show=True,
                show_splash=False,
                flush_startup_observability=True,
                on_services_ready=self._receive_services,
            )
            self.app.setQuitOnLastWindowClosed(False)
            self.pump_events()
            if not self.window.isVisible():
                raise HeadedBenchmarkError("headed_main_window_not_visible")
            self._install_bounded_llm_gateway(bounded_llm)
            self.harness = self.runtime_services.agent.harness  # noqa: SLF001
            self.datasets = self.runtime_services.agent.datasets  # noqa: SLF001
            self.artifacts = self.runtime_services.agent.artifacts  # noqa: SLF001
            self.preparation_services = BenchmarkCasePreparationServices(
                knowledge_import=_HeadedKnowledgeImportAccess(self),
                knowledge_derivation=_HeadedKnowledgeDerivationAccess(self),
                knowledge_index=_HeadedKnowledgeIndexAccess(self),
            )
            self._checks.append(
                OutcomeCheck(
                    "headed_main_window_visible",
                    True,
                    "real_main_window_shown",
                )
            )
        except Exception:
            self._restore_app_home()
            raise

    def pump_events(self) -> None:
        self.app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)

    def wait_for_value(
        self,
        supplier: Callable[[], Any | None],
        *,
        timeout: float,
        error_code: str,
    ) -> Any:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump_events()
            value = supplier()
            if value is not None:
                return value
            time.sleep(0.02)
        raise HeadedBenchmarkError(error_code)

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout: float,
        error_code: str,
    ) -> None:
        self.wait_for_value(
            lambda: True if predicate() else None,
            timeout=timeout,
            error_code=error_code,
        )

    def _receive_services(self, services: ApplicationServices) -> None:
        self.runtime_services = services

    def _button(self, semantic_id: str) -> QPushButton:
        for button in self.window.findChildren(QPushButton):
            if button.accessibleIdentifier() == semantic_id:
                return button
        raise HeadedBenchmarkError("headed_control_unavailable")

    def create_thread(self, *, title: str, fq_model_key: str) -> str:
        QTest.mouseClick(
            self._button("main.history.new-thread"),  # noqa: SLF001
            Qt.MouseButton.LeftButton,
        )
        self.wait_until(
            lambda: self.window.conversation_thread_id is not None,
            timeout=10.0,
            error_code="headed_thread_creation_failed",
        )
        thread_id = str(self.window.conversation_thread_id)
        snapshot = self.harness.rename_thread(thread_id, title)
        self.window.refresh_history(selected_thread_id=thread_id)  # noqa: SLF001
        self._select_model(fq_model_key)
        if snapshot.thread.id != thread_id:
            raise HeadedBenchmarkError("headed_thread_identity_mismatch")
        return thread_id

    def import_knowledge_file(self, source_path: Path, *, timeout: float) -> Any:
        path = source_path.expanduser().resolve(strict=True)
        QTest.mouseClick(
            self._button("main.header.knowledge"),  # noqa: SLF001
            Qt.MouseButton.LeftButton,
        )
        workspace = self.wait_for_value(
            lambda: self.window.findChild(KnowledgeWorkspaceDialog),  # noqa: SLF001
            timeout=10.0,
            error_code="headed_knowledge_workspace_unavailable",
        )
        self.wait_until(
            workspace.isVisible,
            timeout=10.0,
            error_code="headed_knowledge_workspace_not_visible",
        )
        service = self.runtime_services.knowledge_import  # noqa: SLF001
        before_ids = {item.import_id for item in service.list_imports()}
        self._drop_local_files(workspace._documents.viewport(), (path,))  # noqa: SLF001

        imported_view = self.wait_for_value(
            lambda: next(
                (
                    item
                    for item in service.list_imports()
                    if item.import_id not in before_ids
                ),
                None,
            ),
            timeout=10.0,
            error_code="headed_knowledge_drop_not_queued",
        )
        import_id = imported_view.import_id

        def terminal_import() -> Any | None:
            return next(
                (
                    item
                    for item in service.list_imports()
                    if item.import_id == import_id
                    and item.status not in {"queued", "running"}
                ),
                None,
            )

        final_view = self.wait_for_value(
            terminal_import,
            timeout=timeout,
            error_code="headed_knowledge_import_timeout",
        )
        if final_view.status in {"failed", "needs_attention", "cancelled"}:
            raise HeadedBenchmarkError(
                final_view.error_code or "headed_knowledge_import_failed"
            )
        result = service.wait_for_import(import_id, timeout=1.0)
        self._knowledge_results[import_id] = result
        return result

    def execute_submission(
        self,
        *,
        submission: Any,
        measurements: Any,
        case: BenchmarkCase,
        services: BenchmarkCaseServices,
    ) -> None:
        thread_id = str(getattr(submission, "thread_id", "") or "")
        if thread_id != self.window.conversation_thread_id:
            raise HeadedBenchmarkError("headed_submission_thread_mismatch")
        fq_model_key = str(getattr(submission, "fq_model_key", "") or "")
        self._select_model(fq_model_key)

        attachments = tuple(
            Path(item.file_path).expanduser().resolve(strict=True)
            for item in getattr(submission, "source_attachments", ())
        )
        if attachments:
            view = self.window._thread_detail_view  # noqa: SLF001
            self._drop_local_files(view._editor.viewport(), attachments)  # noqa: SLF001
            expected_paths = {str(path) for path in attachments}
            self.wait_until(
                lambda: (
                    expected_paths.issubset(set(view._attached_files))  # noqa: SLF001
                    and expected_paths.issubset(
                        set(self.window._composer_attachments)  # noqa: SLF001
                    )
                ),
                timeout=10.0,
                error_code="headed_source_drop_not_ready",
            )
            self._checks.append(
                OutcomeCheck(
                    "headed_source_files_dropped",
                    True,
                    "real_composer_file_drop_accepted",
                )
            )

        view = self.window._thread_detail_view  # noqa: SLF001
        view._editor.setPlainText(str(getattr(submission, "text", "") or ""))  # noqa: SLF001
        harness_failure: list[object] = []

        def observe(event: Any) -> None:
            measurements.observe(event, case=case, services=services)

        def record_failure(failure: object) -> None:
            harness_failure.append(failure)

        self.window._harness_stream_event.connect(observe)  # noqa: SLF001
        self.window._harness_failed.connect(record_failure)  # noqa: SLF001
        try:
            QTest.mouseClick(view._send_button, Qt.MouseButton.LeftButton)  # noqa: SLF001
            self.wait_until(
                lambda: measurements.final_snapshot_seen or bool(harness_failure),
                timeout=_SUBJECT_TURN_TIMEOUT_SECONDS,
                error_code="headed_subject_turn_timeout",
            )
            if harness_failure and not measurements.final_snapshot_seen:
                error_code = getattr(harness_failure[-1], "error_code", None)
                raise HeadedBenchmarkError(
                    error_code
                    if isinstance(error_code, str) and error_code.strip()
                    else "headed_subject_turn_failed"
                )
            self.wait_until(
                lambda: (
                    not view._running  # noqa: SLF001
                    and self.window.conversation_idle
                ),
                timeout=10.0,
                error_code="headed_ui_did_not_settle",
            )
        finally:
            self.window._harness_stream_event.disconnect(observe)  # noqa: SLF001
            self.window._harness_failed.disconnect(record_failure)  # noqa: SLF001

        snapshot = measurements.snapshot
        messages = list(getattr(snapshot, "messages", ())) if snapshot is not None else []
        terminal = messages[-1] if messages else None
        terminal_id = str(getattr(terminal, "id", "") or "")
        rendered = bool(
            terminal_id
            and terminal_id in view._message_bubbles_by_id  # noqa: SLF001
            and view._message_bubbles_by_id[terminal_id].isVisible()  # noqa: SLF001
        )
        self._checks.append(
            OutcomeCheck(
                "headed_terminal_assistant_rendered",
                rendered,
                (
                    "terminal_assistant_visible_in_chat"
                    if rendered
                    else "terminal_assistant_not_visible_in_chat"
                ),
            )
        )

    def integrity_checks(self) -> tuple[OutcomeCheck, ...]:
        return tuple(self._checks)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._capture_knowledge_integrity()
            runtime_database_path = database_path(self.paths)
            self.window.close()
            self.pump_events()
            window_closed = not self.window.isVisible()
            self._checks.append(
                OutcomeCheck(
                    "headed_main_window_closed",
                    window_closed,
                    (
                        "window_and_runtime_shutdown_completed"
                        if window_closed
                        else "main_window_remained_visible"
                    ),
                )
            )
            self.window.deleteLater()
            QApplication.sendPostedEvents(
                None,
                QEvent.Type.DeferredDelete,
            )
            self.pump_events()
            self.preparation_services = None
            self.harness = None
            self.datasets = None
            self.artifacts = None
            self.window = None
            gc.collect()
            database_ok = self._database_is_readable(runtime_database_path)
            self._checks.append(
                OutcomeCheck(
                    "headed_runtime_database_readable",
                    database_ok,
                    (
                        "sqlite_integrity_check_ok"
                        if database_ok
                        else "sqlite_integrity_check_failed"
                    ),
                )
            )
        finally:
            self._restore_app_home()

    def _select_model(self, fq_model_key: str) -> None:
        picker = self.window._thread_detail_view._model_picker  # noqa: SLF001
        index = picker.findData(fq_model_key)
        if index < 0:
            raise HeadedBenchmarkError("headed_model_not_available")
        picker.setCurrentIndex(index)
        self.pump_events()
        thread_id = self.window.conversation_thread_id
        if thread_id is None:
            raise HeadedBenchmarkError("headed_thread_not_selected")
        selected = self.harness.get_thread_snapshot(thread_id).thread.selected_fq_model_key
        if selected != fq_model_key:
            raise HeadedBenchmarkError("headed_model_selection_failed")

    def _install_bounded_llm_gateway(self, bounded_llm: LLMService) -> None:
        harness = self.runtime_services.agent.harness  # noqa: SLF001
        conversation = harness._conversation_service  # noqa: SLF001
        targets = (
            (self.window, "_llm_service"),
            (harness, "_llm_service"),
            (conversation, "_llm_service"),
        )
        originals: list[tuple[Any, str, Any]] = []
        try:
            for owner, attribute in targets:
                if not hasattr(owner, attribute):
                    raise HeadedBenchmarkError("headed_llm_gateway_seam_missing")
                originals.append((owner, attribute, getattr(owner, attribute)))
                setattr(owner, attribute, bounded_llm)
            if any(getattr(owner, attribute) is not bounded_llm for owner, attribute in targets):
                raise HeadedBenchmarkError("headed_llm_gateway_install_failed")
        except Exception:
            for owner, attribute, original in reversed(originals):
                setattr(owner, attribute, original)
            raise

    def _drop_local_files(self, target: Any, paths: tuple[Path, ...]) -> None:
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        drag_event = QDragEnterEvent(
            QPoint(8, 8),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(target, drag_event)
        if not drag_event.isAccepted():
            raise HeadedBenchmarkError("headed_file_drag_rejected")
        drop_event = QDropEvent(
            QPointF(8, 8),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(target, drop_event)
        self.pump_events()
        if not drop_event.isAccepted():
            raise HeadedBenchmarkError("headed_file_drop_rejected")

    def _capture_knowledge_integrity(self) -> None:
        if not self._knowledge_results:
            return
        workspace = self.window.findChild(KnowledgeWorkspaceDialog)  # noqa: SLF001
        expected_document_ids = {
            result.document_id for result in self._knowledge_results.values()
        }
        workspace.refresh_documents()
        try:
            self.wait_until(
                lambda: (
                    workspace._last_documents is not None  # noqa: SLF001
                    and expected_document_ids.issubset(
                        {
                            item.document_id
                            for item in workspace._last_documents.items  # noqa: SLF001
                        }
                    )
                ),
                timeout=30.0,
                error_code="headed_knowledge_document_not_visible",
            )
            documents_visible = True
        except HeadedBenchmarkError:
            documents_visible = False
        self._checks.append(
            OutcomeCheck(
                "headed_knowledge_document_visible",
                documents_visible,
                (
                    "imported_document_visible_in_workspace"
                    if documents_visible
                    else "imported_document_missing_from_workspace"
                ),
            )
        )

        task_query = self.runtime_services.knowledge_tasks  # noqa: SLF001
        try:
            self.wait_until(
                lambda: not task_query.summary().has_active_work,
                timeout=120.0,
                error_code="headed_knowledge_tasks_not_terminal",
            )
            tasks_terminal = True
        except HeadedBenchmarkError:
            tasks_terminal = False
        queue_dialog = workspace._queue_dialog  # noqa: SLF001
        queue_surface_used = queue_dialog is not None
        self._checks.append(
            OutcomeCheck(
                "headed_knowledge_task_queue_terminal",
                queue_surface_used and tasks_terminal,
                (
                    "task_queue_opened_and_tasks_terminal"
                    if queue_surface_used and tasks_terminal
                    else "task_queue_missing_or_tasks_active"
                ),
            )
        )

    @staticmethod
    def _database_is_readable(database_path: Path) -> bool:
        if not database_path.is_file():
            return False
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                f"{database_path.resolve().as_uri()}?mode=ro",
                uri=True,
            )
            row = connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error:
            return False
        finally:
            if connection is not None:
                connection.close()
        return row == ("ok",)

    def _restore_app_home(self) -> None:
        if self._previous_app_home is None:
            os.environ.pop("XENIX_APP_HOME", None)
        else:
            os.environ["XENIX_APP_HOME"] = self._previous_app_home
