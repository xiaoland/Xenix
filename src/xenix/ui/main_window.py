from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.agent import (
    AgentHarnessService,
    AgentHarnessStreamEvent,
    ContinueStepBudgetInput,
    DatasetAttachmentInput,
    SubmitUserTurnInput,
    ThreadSnapshot,
)
from ..services.artifact_service import ArtifactService
from ..services.dataset_service import DatasetService, RegisterDatasetInput
from ..services.llm import LLMService, LLMSettingsService
from ..services.ml.worker_settings import MLWorkerSettingsService
from .chatbot import ComposerAttachmentStatus, ThreadDetailView
from .icons import plus_icon
from .layout_debug import dump_layout_if_enabled
from .native_widgets import emphasize_label
from .settings_dialog import SettingsDialog
from .tool_call_detail_view import ToolCallDetailView

if TYPE_CHECKING:
    from ..services.ml_service import MLService


@dataclass(frozen=True)
class _AttachmentPreflightSucceeded:
    preflight_id: str
    path: str
    attachment: DatasetAttachmentInput


@dataclass(frozen=True)
class _AttachmentPreflightFailed:
    preflight_id: str
    path: str
    message: str


@dataclass
class _ComposerAttachmentRecord:
    path: str
    preflight_id: str
    attachment: DatasetAttachmentInput | None = None


class MainWindow(QMainWindow):
    _harness_failed = Signal(str)
    _harness_stream_event = Signal(object)
    _attachment_preflight_succeeded = Signal(object)
    _attachment_preflight_failed = Signal(object)
    _thread_title_generated = Signal(str, str)
    _thread_title_generation_failed = Signal(str, str)

    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        agent_harness_service: AgentHarnessService,
        llm_service: LLMService,
        llm_settings_service: LLMSettingsService,
        ml_worker_settings_service: MLWorkerSettingsService,
        artifact_service: ArtifactService,
        dataset_service: DatasetService,
        ml_service: MLService,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._agent_harness_service = agent_harness_service
        self._llm_service = llm_service
        self._llm_settings_service = llm_settings_service
        self._ml_worker_settings_service = ml_worker_settings_service
        self._artifact_service = artifact_service
        self._dataset_service = dataset_service
        self._ml_service = ml_service
        self._agent_thread_id: str | None = None
        self._active_agent_run_id: str | None = None
        self._composer_attachments: dict[str, _ComposerAttachmentRecord] = {}
        self._cancelled_attachment_preflight_ids: set[str] = set()
        self._pending_step_confirmation: AgentHarnessStreamEvent | None = None
        self._cancelled_agent_run_ids: set[str] = set()
        self._settings_dialog: SettingsDialog | None = None
        self._tool_call_detail_views: list[ToolCallDetailView] = []
        self._thread_title_progress_dialog: QProgressDialog | None = None

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
        self._new_thread_button.setIcon(plus_icon())
        self._new_thread_button.setIconSize(QSize(14, 14))
        self._new_thread_button.clicked.connect(self._create_agent_thread)
        self._history_list = QListWidget(parent=self._history_sidebar)
        self._history_list.itemClicked.connect(self._open_history_thread)
        self._history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._history_list.customContextMenuRequested.connect(self._open_history_item_menu)
        self._refreshing_history = False

        self._thread_detail_view = ThreadDetailView(parent=self)
        self._thread_detail_view.set_artifact_resolver(self._artifact_service.resolve_uri)
        self._thread_detail_view.message_submitted.connect(self._submit_chat_message)
        self._thread_detail_view.files_attached.connect(self._start_attachment_preflights)
        self._thread_detail_view.attachment_removed.connect(self._discard_composer_attachment)
        self._thread_detail_view.model_selected.connect(self._update_thread_model)
        self._thread_detail_view.artifact_link_activated.connect(self._open_artifact_link)
        self._thread_detail_view.tool_action_requested.connect(self._handle_tool_action)
        self._thread_detail_view.stop_requested.connect(self._request_harness_stop)
        self._thread_detail_view.step_budget_continue_requested.connect(self._continue_step_budget)
        self._thread_detail_view.step_budget_stop_requested.connect(self._stop_step_budget)
        self._harness_failed.connect(self._render_harness_error)
        self._harness_stream_event.connect(self._render_harness_stream_event)
        self._attachment_preflight_succeeded.connect(self._finish_attachment_preflight)
        self._attachment_preflight_failed.connect(self._fail_attachment_preflight)
        self._thread_title_generated.connect(self._finish_generated_thread_title)
        self._thread_title_generation_failed.connect(self._fail_generated_thread_title)

        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()
        self._sync_model_picker_options()

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
        self._new_thread_button.setText("")
        self._new_thread_button.setToolTip(self.tr("New thread"))
        self._thread_detail_view.retranslate_ui()
        if self._settings_dialog is not None:
            self._settings_dialog.retranslate_ui()
        self._sync_model_picker_options()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _sync_model_picker_options(self) -> None:
        options = [
            (option.fq_model_key, option.label)
            for option in self._llm_service.model_options()
        ]
        selected = None
        if self._agent_thread_id is not None:
            try:
                selected = self._agent_harness_service.get_thread_snapshot(
                    self._agent_thread_id
                ).thread.selected_fq_model_key
            except Exception:
                selected = None
        self._thread_detail_view.set_model_options(
            options,
            selected_fq_model_key=selected or self._llm_service.default_fq_model_key(),
        )

    def _sync_thread_model_picker(self, snapshot: ThreadSnapshot) -> None:
        selected = snapshot.thread.selected_fq_model_key or self._llm_service.default_fq_model_key()
        self._thread_detail_view.set_selected_fq_model_key(selected)

    def _update_thread_model(self, fq_model_key: str) -> None:
        if self._agent_thread_id is None:
            return
        try:
            snapshot = self._agent_harness_service.set_thread_model(self._agent_thread_id, fq_model_key)
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))
            return
        self._sync_thread_model_picker(snapshot)

    def _open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(
                paths=self._paths,
                log_path=self._log_path,
                db_path=self._db_path,
                translation_manager=self._translation_manager,
                llm_service=self._llm_service,
                llm_settings_service=self._llm_settings_service,
                ml_worker_settings_service=self._ml_worker_settings_service,
                parent=self,
            )
            self._settings_dialog.agent_settings_saved.connect(self._reload_agent_provider)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _submit_chat_message(self, text: str, file_paths: list[str], fq_model_key: str) -> None:
        self._pending_step_confirmation = None
        self._thread_detail_view.clear_step_confirmation()
        dataset_attachments = self._ready_composer_attachments(file_paths)
        if len(dataset_attachments) != len(file_paths):
            return

        self._start_harness_submission(
            text=text,
            dataset_attachments=dataset_attachments,
            fq_model_key=fq_model_key,
            interface_locale=self._translation_manager.current_locale(),
        )
        for file_path in file_paths:
            self._composer_attachments.pop(str(Path(file_path).resolve()), None)

    def _start_attachment_preflights(self, file_paths: list[str]) -> None:
        for file_path in file_paths:
            self._start_attachment_preflight(file_path)

    def _start_attachment_preflight(self, file_path: str) -> None:
        source_path = Path(file_path).expanduser().resolve()
        normalized_path = str(source_path)
        if normalized_path in self._composer_attachments:
            return
        preflight_id = uuid4().hex
        self._composer_attachments[normalized_path] = _ComposerAttachmentRecord(
            path=normalized_path,
            preflight_id=preflight_id,
        )
        self._thread_detail_view.set_attachment_status(
            normalized_path,
            ComposerAttachmentStatus.PENDING,
        )

        def run_preflight() -> None:
            try:
                attachment = self._register_composer_dataset(normalized_path)
            except Exception as exc:
                self._attachment_preflight_failed.emit(
                    _AttachmentPreflightFailed(
                        preflight_id=preflight_id,
                        path=normalized_path,
                        message=str(exc),
                    )
                )
                return
            self._attachment_preflight_succeeded.emit(
                _AttachmentPreflightSucceeded(
                    preflight_id=preflight_id,
                    path=normalized_path,
                    attachment=attachment,
                )
            )

        threading.Thread(target=run_preflight, name="xenix-attachment-preflight", daemon=True).start()

    def _finish_attachment_preflight(self, result: object) -> None:
        if not isinstance(result, _AttachmentPreflightSucceeded):
            return
        if result.preflight_id in self._cancelled_attachment_preflight_ids:
            self._cancelled_attachment_preflight_ids.discard(result.preflight_id)
            self._discard_registered_attachment(result.attachment)
            return
        record = self._composer_attachments.get(result.path)
        if record is None or record.preflight_id != result.preflight_id:
            self._discard_registered_attachment(result.attachment)
            return
        record.attachment = result.attachment
        self._thread_detail_view.set_attachment_status(
            result.path,
            ComposerAttachmentStatus.READY,
        )

    def _fail_attachment_preflight(self, result: object) -> None:
        if not isinstance(result, _AttachmentPreflightFailed):
            return
        if result.preflight_id in self._cancelled_attachment_preflight_ids:
            self._cancelled_attachment_preflight_ids.discard(result.preflight_id)
            return
        record = self._composer_attachments.get(result.path)
        if record is None or record.preflight_id != result.preflight_id:
            return
        self._thread_detail_view.set_attachment_status(
            result.path,
            ComposerAttachmentStatus.FAILED,
            error=result.message,
        )
        self._thread_detail_view.show_error(result.message)

    def _start_harness_submission(
        self,
        *,
        text: str,
        dataset_attachments: list[DatasetAttachmentInput],
        fq_model_key: str,
        interface_locale: str,
    ) -> None:
        try:
            submit_input = SubmitUserTurnInput(
                thread_id=self._agent_thread_id,
                text=text,
                dataset_attachments=dataset_attachments,
                fq_model_key=fq_model_key or None,
                interface_locale=interface_locale,
            )
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))
            self._thread_detail_view.set_running(False)
            return

        user_blocks = []
        if text:
            user_blocks.append({"type": "text", "text": text})
        for attachment in dataset_attachments:
            user_blocks.append({"type": "dataset", **attachment.model_dump(mode="json")})
        self._thread_detail_view.add_user_message(user_blocks)
        self._thread_detail_view.set_running(True)

        def run_harness() -> None:
            try:
                for event in self._agent_harness_service.submit_user_turn_stream(submit_input):
                    self._harness_stream_event.emit(event)
            except Exception as exc:
                self._harness_failed.emit(str(exc))

        threading.Thread(target=run_harness, name="xenix-agent-harness", daemon=True).start()

    def _register_composer_dataset(self, file_path: str) -> DatasetAttachmentInput:
        source_path = Path(file_path).expanduser().resolve()
        attachment = self._dataset_service.register_dataset_attachment(
            RegisterDatasetInput(source_path=str(source_path), name=source_path.stem)
        )
        return DatasetAttachmentInput(
            dataset_id=attachment.dataset_id,
            name=attachment.name,
            file_name=attachment.file_name,
            source_format=attachment.source_format,
            row_count=attachment.row_count,
            column_count=attachment.column_count,
            preview_columns=attachment.preview_columns,
        )

    def _ready_composer_attachments(self, file_paths: list[str]) -> list[DatasetAttachmentInput]:
        attachments: list[DatasetAttachmentInput] = []
        for file_path in file_paths:
            record = self._composer_attachments.get(str(Path(file_path).resolve()))
            if record is None or record.attachment is None:
                continue
            attachments.append(record.attachment)
        return attachments

    def _discard_composer_attachment(self, file_path: str) -> None:
        record = self._composer_attachments.pop(str(Path(file_path).resolve()), None)
        if record is None:
            return
        if record.attachment is None:
            self._cancelled_attachment_preflight_ids.add(record.preflight_id)
            return
        self._discard_registered_attachment(record.attachment)

    def _discard_registered_attachment(self, attachment: DatasetAttachmentInput) -> None:
        try:
            self._dataset_service.discard_unreferenced_dataset(attachment.dataset_id)
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))

    def _render_harness_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self._agent_thread_id = snapshot.thread.id
        self._active_agent_run_id = None
        self._pending_step_confirmation = None
        self._sync_thread_model_picker(snapshot)
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
            self._sync_thread_model_picker(event.snapshot)
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

    def _handle_tool_action(self, action: object) -> None:
        if not isinstance(action, dict):
            return
        action_type = str(action.get("type") or "")
        raw_task_ids = action.get("task_ids")
        if not isinstance(raw_task_ids, list):
            return
        task_ids = [str(task_id) for task_id in raw_task_ids if str(task_id).strip()]
        if not task_ids:
            return
        if action_type == "open_tool_call_detail":
            self._open_tool_call_detail(task_ids)

    def _open_tool_call_detail(self, task_ids: list[str]) -> None:
        view = ToolCallDetailView(
            ml_service=self._ml_service,
            task_ids=task_ids,
            parent=self,
        )
        view.destroyed.connect(lambda _obj=None, view=view: self._forget_tool_call_detail_view(view))
        self._tool_call_detail_views.append(view)
        view.show()
        view.raise_()
        view.activateWindow()

    def _forget_tool_call_detail_view(self, view: ToolCallDetailView) -> None:
        if view in self._tool_call_detail_views:
            self._tool_call_detail_views.remove(view)

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
            self._sync_thread_model_picker(event.snapshot)
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
        self._agent_harness_service.set_provider(self._llm_service.build_provider())
        self._agent_harness_service.set_turn_completion_guard_provider(
            self._llm_service.build_turn_completion_guard_provider()
        )
        self._agent_harness_service.set_thread_title_provider(
            self._llm_service.build_thread_title_provider()
        )
        self._sync_model_picker_options()

    def _create_agent_thread(self) -> None:
        self._pending_step_confirmation = None
        self._active_agent_run_id = None
        self._thread_detail_view.clear_step_confirmation()
        snapshot = self._agent_harness_service.create_thread(
            interface_locale=self._translation_manager.current_locale(),
        )
        self._agent_thread_id = snapshot.thread.id
        self._sync_thread_model_picker(snapshot)
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
        self._sync_thread_model_picker(snapshot)
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
        generate_title_action = menu.addAction(self.tr("Generate title..."))
        copy_thread_id_action = menu.addAction(self.tr("Copy thread ID"))
        delete_action = menu.addAction(self.tr("Delete"))
        selected_action = menu.exec(self._history_list.viewport().mapToGlobal(position))

        if selected_action is rename_action:
            self._rename_history_thread(item)
        elif selected_action is generate_title_action:
            self._generate_history_thread_title(item)
        elif selected_action is copy_thread_id_action:
            self._copy_history_thread_id(item)
        elif selected_action is delete_action:
            self._delete_history_thread(item)

    def _copy_history_thread_id(self, item: QListWidgetItem) -> None:
        thread_id = self._thread_id_from_history_item(item)
        if thread_id is None:
            return
        QApplication.clipboard().setText(thread_id)

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

    def _generate_history_thread_title(self, item: QListWidgetItem) -> None:
        thread_id = self._thread_id_from_history_item(item)
        if thread_id is None:
            return
        if not self._agent_harness_service.has_thread_title_provider():
            QMessageBox.information(
                self,
                self.tr("Generate Thread Title"),
                self.tr("Thread title model is not configured."),
            )
            return

        self._show_thread_title_progress()

        def run_title_generation() -> None:
            try:
                title = self._agent_harness_service.generate_thread_title(thread_id)
            except Exception as exc:
                self._thread_title_generation_failed.emit(thread_id, str(exc))
                return
            self._thread_title_generated.emit(thread_id, title)

        threading.Thread(
            target=run_title_generation,
            name="xenix-thread-title-generation",
            daemon=True,
        ).start()

    def _show_thread_title_progress(self) -> None:
        self._close_thread_title_progress()
        dialog = QProgressDialog(
            self.tr("Generating thread title..."),
            "",
            0,
            0,
            self,
        )
        dialog.setObjectName("threadTitleProgressDialog")
        dialog.setWindowTitle(self.tr("Generate Thread Title"))
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setCancelButton(None)
        self._thread_title_progress_dialog = dialog
        dialog.show()

    def _close_thread_title_progress(self) -> None:
        if self._thread_title_progress_dialog is None:
            return
        dialog = self._thread_title_progress_dialog
        self._thread_title_progress_dialog = None
        dialog.close()
        dialog.deleteLater()

    def _finish_generated_thread_title(self, thread_id: str, proposal: str) -> None:
        self._close_thread_title_progress()
        title, accepted = QInputDialog.getText(
            self,
            self.tr("Apply Generated Title"),
            self.tr("Thread name"),
            text=proposal,
        )
        if not accepted:
            return
        try:
            snapshot = self._agent_harness_service.rename_thread(thread_id, title.strip() or None)
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr("Generate Thread Title"),
                str(exc),
            )
            return
        self._refresh_history_sidebar(selected_thread_id=snapshot.thread.id)

    def _fail_generated_thread_title(self, _thread_id: str, message: str) -> None:
        self._close_thread_title_progress()
        QMessageBox.warning(
            self,
            self.tr("Generate Thread Title"),
            message,
        )

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
