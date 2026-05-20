from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.agent import (
    AgentHarnessService,
    AgentHarnessStreamEvent,
    AgentSettingsService,
    ContinueStepBudgetInput,
    SubmitUserTurnInput,
    ThreadSnapshot,
)
from ..services.artifact_service import ArtifactService
from .chatbot import ThreadDetailView
from .layout_debug import dump_layout_if_enabled
from .native_widgets import emphasize_label
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    _harness_failed = Signal(str)
    _harness_stream_event = Signal(object)

    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        agent_harness_service: AgentHarnessService,
        agent_settings_service: AgentSettingsService,
        artifact_service: ArtifactService,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._agent_harness_service = agent_harness_service
        self._agent_settings_service = agent_settings_service
        self._artifact_service = artifact_service
        self._agent_thread_id: str | None = None
        self._active_agent_run_id: str | None = None
        self._pending_step_confirmation: AgentHarnessStreamEvent | None = None
        self._cancelled_agent_run_ids: set[str] = set()
        self._settings_dialog: SettingsDialog | None = None

        self._title_label = QLabel(parent=self)
        self._settings_button = QPushButton(parent=self)
        self._settings_button.clicked.connect(self._open_settings)

        self._history_sidebar = QFrame(parent=self)
        self._history_sidebar.setObjectName("historySidebar")
        self._history_sidebar.setFrameShape(QFrame.StyledPanel)
        self._history_label = QLabel(parent=self._history_sidebar)
        self._new_thread_button = QPushButton(parent=self._history_sidebar)
        self._new_thread_button.setObjectName("newThreadButton")
        self._new_thread_button.setFixedSize(28, 28)
        self._new_thread_button.clicked.connect(self._create_agent_thread)
        self._history_list = QListWidget(parent=self._history_sidebar)
        self._history_list.itemClicked.connect(self._open_history_thread)
        self._history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._history_list.customContextMenuRequested.connect(self._open_history_item_menu)
        self._refreshing_history = False

        self._thread_detail_view = ThreadDetailView(parent=self)
        self._thread_detail_view.message_submitted.connect(self._submit_chat_message)
        self._thread_detail_view.artifact_link_activated.connect(self._open_artifact_link)
        self._thread_detail_view.stop_requested.connect(self._request_harness_stop)
        self._thread_detail_view.step_budget_continue_requested.connect(self._continue_step_budget)
        self._thread_detail_view.step_budget_stop_requested.connect(self._stop_step_budget)
        self._harness_failed.connect(self._render_harness_error)
        self._harness_stream_event.connect(self._render_harness_stream_event)

        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("mainWindowRoot")
        layout = QVBoxLayout(root)
        layout.setObjectName("mainWindowRootLayout")
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setObjectName("mainHeaderLayout")
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        emphasize_label(self._title_label, point_delta=2)
        self._settings_button.setMinimumWidth(96)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self._settings_button)
        layout.addLayout(header_layout)

        sidebar_layout = QVBoxLayout(self._history_sidebar)
        sidebar_layout.setObjectName("historySidebarLayout")
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(8)
        self._history_sidebar.setFixedWidth(248)
        self._history_label.setObjectName("historySidebarTitle")
        self._history_list.setObjectName("historyList")
        history_header_layout = QHBoxLayout()
        history_header_layout.setObjectName("historyHeaderLayout")
        history_header_layout.setContentsMargins(0, 0, 0, 0)
        history_header_layout.setSpacing(8)
        history_header_layout.addWidget(self._history_label)
        history_header_layout.addStretch(1)
        history_header_layout.addWidget(self._new_thread_button)
        sidebar_layout.addLayout(history_header_layout)
        sidebar_layout.addWidget(self._history_list, 1)

        content_layout = QHBoxLayout()
        content_layout.setObjectName("mainContentLayout")
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._history_sidebar)
        content_layout.addWidget(self._thread_detail_view, 1)
        layout.addLayout(content_layout, 1)

        self.setCentralWidget(root)
        self._refresh_history_sidebar()
        current_item = self._history_list.currentItem()
        if current_item is not None:
            self._open_history_thread(current_item)
        dump_layout_if_enabled(root, reason="main-window-setup")

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Xenix Native"))
        self._title_label.setText(self.tr("Xenix"))
        self._settings_button.setText(self.tr("Settings"))
        self._history_label.setText(self.tr("History"))
        self._new_thread_button.setText("+")
        self._new_thread_button.setToolTip(self.tr("New thread"))
        if self._settings_dialog is not None:
            self._settings_dialog.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(
                paths=self._paths,
                log_path=self._log_path,
                db_path=self._db_path,
                translation_manager=self._translation_manager,
                agent_settings_service=self._agent_settings_service,
                parent=self,
            )
            self._settings_dialog.agent_settings_saved.connect(self._reload_agent_provider)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _submit_chat_message(self, text: str, file_paths: list[str]) -> None:
        self._pending_step_confirmation = None
        self._thread_detail_view.clear_step_confirmation()
        user_blocks = []
        if text:
            user_blocks.append({"type": "text", "text": text})
        for file_path in file_paths:
            user_blocks.append({"type": "file", "path": file_path})
        self._thread_detail_view.add_user_message(user_blocks)
        self._thread_detail_view.set_running(True)

        def run_harness() -> None:
            try:
                for event in self._agent_harness_service.submit_user_turn_stream(
                    SubmitUserTurnInput(
                        thread_id=self._agent_thread_id,
                        text=text,
                        file_paths=file_paths,
                    )
                ):
                    self._harness_stream_event.emit(event)
            except Exception as exc:
                self._harness_failed.emit(str(exc))

        threading.Thread(target=run_harness, name="xenix-agent-harness", daemon=True).start()

    def _render_harness_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self._agent_thread_id = snapshot.thread.id
        self._active_agent_run_id = None
        self._pending_step_confirmation = None
        self._thread_detail_view.hide_thinking_indicator()
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))
        self._thread_detail_view.clear_step_confirmation()
        self._thread_detail_view.set_running(False)
        self._refresh_history_sidebar(selected_thread_id=snapshot.thread.id)

    def _render_harness_stream_event(self, event) -> None:
        if event.run_id in self._cancelled_agent_run_ids and event.kind != "snapshot":
            return
        if event.kind == "snapshot" and event.snapshot is not None:
            if event.is_final:
                if event.run_id is not None:
                    self._cancelled_agent_run_ids.discard(event.run_id)
                self._render_harness_snapshot(event.snapshot)
                return
            self._agent_thread_id = event.snapshot.thread.id
            self._active_agent_run_id = event.run_id
            self._thread_detail_view.render_events(
                event.chatbot_events
                if event.chatbot_events is not None
                else self._agent_harness_service.project_chatbot_events(event.snapshot)
            )
            self._refresh_history_sidebar(selected_thread_id=event.snapshot.thread.id)
            return
        if event.kind == "chatbot_event" and event.chatbot_event is not None:
            self._thread_detail_view.apply_chatbot_event(event.chatbot_event)
            return
        if event.kind == "step_confirmation_required":
            self._render_step_confirmation(event)
            return
        if event.kind in {"message_created", "message_updated", "message_finalized"}:
            if event.chatbot_event is not None:
                self._thread_detail_view.apply_chatbot_event(event.chatbot_event)
            elif event.message is not None:
                self._thread_detail_view.apply_message_event(event.message)
            return

    def _render_harness_error(self, message: str) -> None:
        self._pending_step_confirmation = None
        self._thread_detail_view.clear_step_confirmation()
        self._thread_detail_view.hide_thinking_indicator()
        self._thread_detail_view.show_error(message)
        self._thread_detail_view.set_running(False)

    def _open_artifact_link(self, uri: str) -> None:
        url = QUrl(uri)
        if url.scheme() != "artifact":
            opened = QDesktopServices.openUrl(url)
            if not opened:
                self._thread_detail_view.show_error(self.tr("Could not open link: {uri}").format(uri=uri))
            return
        try:
            artifact = self._artifact_service.resolve_uri(uri)
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))
            return
        if not artifact.ready_to_open:
            self._thread_detail_view.show_error(self.tr("Artifact is not ready to open."))
            return
        if not artifact.exists:
            self._thread_detail_view.show_error(self.tr("Artifact file is missing: {path}").format(path=artifact.absolute_path))
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(artifact.absolute_path))
        if not opened:
            self._thread_detail_view.show_error(self.tr("Could not open artifact: {path}").format(path=artifact.absolute_path))

    def _request_harness_stop(self) -> None:
        if self._active_agent_run_id is not None:
            self._agent_harness_service.cancel_run(self._active_agent_run_id)
            self._cancelled_agent_run_ids.add(self._active_agent_run_id)
        self._thread_detail_view.hide_thinking_indicator()
        self._thread_detail_view.set_running(False)
        self._thread_detail_view.show_error("Stopped.")

    def _render_step_confirmation(self, event: AgentHarnessStreamEvent) -> None:
        if event.snapshot is not None:
            self._agent_thread_id = event.snapshot.thread.id
            self._thread_detail_view.render_events(
                event.chatbot_events
                if event.chatbot_events is not None
                else self._agent_harness_service.project_chatbot_events(event.snapshot)
            )
            self._refresh_history_sidebar(selected_thread_id=event.snapshot.thread.id)
        elif event.thread_id is not None:
            self._agent_thread_id = event.thread_id
            self._refresh_history_sidebar(selected_thread_id=event.thread_id)
        self._pending_step_confirmation = event
        self._active_agent_run_id = None
        self._thread_detail_view.set_running(False)
        self._thread_detail_view.show_step_confirmation(
            self.tr("Step budget used: {used}/{max}. Continue with up to {steps} more steps?").format(
                used=str(event.used_steps),
                max=str(event.max_total_steps),
                steps=str(event.suggested_steps),
            )
        )

    def _continue_step_budget(self) -> None:
        if self._pending_step_confirmation is None:
            return
        pending = self._pending_step_confirmation
        if pending.thread_id is None or pending.turn_id is None or pending.run_id is None:
            return
        self._pending_step_confirmation = None
        self._active_agent_run_id = pending.run_id
        self._cancelled_agent_run_ids.discard(pending.run_id)
        self._thread_detail_view.clear_step_confirmation()
        self._thread_detail_view.set_running(True)

        def run_harness() -> None:
            try:
                for event in self._agent_harness_service.continue_step_budget_stream(
                    ContinueStepBudgetInput(
                        thread_id=pending.thread_id,
                        turn_id=pending.turn_id,
                        run_id=pending.run_id,
                        additional_steps=pending.suggested_steps,
                    )
                ):
                    self._harness_stream_event.emit(event)
            except Exception as exc:
                self._harness_failed.emit(str(exc))

        threading.Thread(target=run_harness, name="xenix-agent-harness-resume", daemon=True).start()

    def _stop_step_budget(self) -> None:
        if self._pending_step_confirmation is None:
            return
        pending = self._pending_step_confirmation
        if pending.thread_id is None or pending.turn_id is None or pending.run_id is None:
            return
        self._pending_step_confirmation = None
        self._active_agent_run_id = None
        self._thread_detail_view.clear_step_confirmation()
        try:
            snapshot = self._agent_harness_service.stop_step_budget_confirmation(
                ContinueStepBudgetInput(
                    thread_id=pending.thread_id,
                    turn_id=pending.turn_id,
                    run_id=pending.run_id,
                    additional_steps=0,
                )
            )
        except Exception as exc:
            self._render_harness_error(str(exc))
            return
        self._render_harness_snapshot(snapshot)

    def _reload_agent_provider(self) -> None:
        self._agent_harness_service.set_provider(self._agent_settings_service.build_provider())
        self._agent_harness_service.set_turn_completion_guard_provider(
            self._agent_settings_service.build_turn_completion_guard_provider()
        )

    def _create_agent_thread(self) -> None:
        self._pending_step_confirmation = None
        self._active_agent_run_id = None
        self._thread_detail_view.clear_step_confirmation()
        snapshot = self._agent_harness_service.create_thread()
        self._agent_thread_id = snapshot.thread.id
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))
        self._refresh_history_sidebar(selected_thread_id=snapshot.thread.id)

    def _refresh_history_sidebar(self, *, selected_thread_id: str | None = None) -> None:
        self._history_list.clear()
        self._refreshing_history = True
        try:
            selected_row = -1
            for index, thread in enumerate(self._agent_harness_service.list_threads()):
                title = thread.title or "Untitled conversation"
                item = QListWidgetItem(title)
                item.setData(Qt.UserRole, thread.id)
                self._history_list.addItem(item)
                if thread.id == selected_thread_id:
                    selected_row = index
            if selected_row >= 0:
                self._history_list.setCurrentRow(selected_row)
            elif selected_thread_id is None and self._agent_thread_id is None and self._history_list.count() > 0:
                self._history_list.setCurrentRow(0)
        finally:
            self._refreshing_history = False

    def _open_history_thread(self, item: QListWidgetItem) -> None:
        if self._refreshing_history:
            return
        thread_id = self._thread_id_from_history_item(item)
        if thread_id is None:
            return
        snapshot = self._agent_harness_service.get_thread_snapshot(thread_id)
        self._agent_thread_id = thread_id
        if self._pending_step_confirmation is not None and self._pending_step_confirmation.thread_id != thread_id:
            self._pending_step_confirmation = None
            self._active_agent_run_id = None
            self._thread_detail_view.clear_step_confirmation()
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))

    def _open_history_item_menu(self, position: QPoint) -> None:
        item = self._history_list.itemAt(position)
        if item is None:
            return

        menu = QMenu(self)
        rename_action = menu.addAction(self.tr("Rename"))
        delete_action = menu.addAction(self.tr("Delete"))
        selected_action = menu.exec(self._history_list.viewport().mapToGlobal(position))

        if selected_action is rename_action:
            self._rename_history_thread(item)
        elif selected_action is delete_action:
            self._delete_history_thread(item)

    def _rename_history_thread(self, item: QListWidgetItem) -> None:
        thread_id = self._thread_id_from_history_item(item)
        if thread_id is None:
            return

        title, accepted = QInputDialog.getText(
            self,
            self.tr("Rename Thread"),
            self.tr("Thread name"),
            text=item.text(),
        )
        if not accepted:
            return

        snapshot = self._agent_harness_service.rename_thread(thread_id, title.strip() or None)
        self._refresh_history_sidebar(selected_thread_id=snapshot.thread.id)

    def _delete_history_thread(self, item: QListWidgetItem) -> None:
        thread_id = self._thread_id_from_history_item(item)
        if thread_id is None:
            return

        if self._thread_detail_view._running and self._agent_thread_id == thread_id:
            QMessageBox.information(
                self,
                self.tr("Delete Thread"),
                self.tr("Stop the current run before deleting this thread."),
            )
            return

        title = item.text()
        response = QMessageBox.question(
            self,
            self.tr("Delete Thread"),
            self.tr('Delete "{title}"? This action cannot be undone.').format(title=title),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return

        deleting_current = self._agent_thread_id == thread_id
        self._agent_harness_service.delete_thread(thread_id)
        if deleting_current:
            self._agent_thread_id = None
            self._pending_step_confirmation = None
            self._active_agent_run_id = None
            self._thread_detail_view.clear_step_confirmation()
            self._thread_detail_view.clear_messages()

        self._refresh_history_sidebar(selected_thread_id=None if deleting_current else self._agent_thread_id)
        if deleting_current:
            current_item = self._history_list.currentItem()
            if current_item is not None:
                self._open_history_thread(current_item)

    def _thread_id_from_history_item(self, item: QListWidgetItem) -> str | None:
        thread_id = item.data(Qt.UserRole)
        return thread_id if isinstance(thread_id, str) else None
