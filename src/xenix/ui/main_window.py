from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import QEvent, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.agent import (
    AgentHarnessService,
    AgentHarnessStreamEvent,
    AttachmentImportStatus,
    SourceAttachmentInput,
    SubmitUserTurnInput,
)
from ..services.artifact_service import ArtifactService
from ..services.link_router import LinkRouter
from ..services.llm import ConversationSnapshot, LLMService
from .chatbot import ComposerAttachmentStatus, ThreadDetailView
from .conversation.execution import SubmissionExecutor, ThreadedSubmissionExecutor
from .conversation.turn_controller import (
    ConversationTurnController,
    FailureRecovery,
    StopDisposition,
    TurnAction,
)
from .layout_debug import dump_layout_if_enabled
from .native_widgets import emphasize_label
from .semantic_identity import identify
from .settings.contracts import SettingsTab
from .history import HistoryPanel, HistoryPort
from .windows.auxiliary import AuxiliaryWindowCoordinator


@dataclass(frozen=True)
class _ServiceLinkActivationSucceeded:
    activation_id: str
    uri: str


@dataclass(frozen=True)
class _ServiceLinkActivationFailed:
    activation_id: str
    uri: str
    message: str


@dataclass
class _ComposerAttachmentRecord:
    path: str
    attachment: SourceAttachmentInput


class MainWindow(QMainWindow):
    closing = Signal()
    _harness_failed = Signal(object)
    _harness_failure_received = Signal(str, object)
    _harness_stream_event = Signal(object)
    _service_link_activation_succeeded = Signal(object)
    _service_link_activation_failed = Signal(object)

    def __init__(
        self,
        *,
        agent_harness_service: AgentHarnessService,
        llm_service: LLMService,
        artifact_service: ArtifactService,
        link_router: LinkRouter,
        current_locale: Callable[[], str],
        history_port: HistoryPort,
        auxiliary_factory: Callable[[QWidget], AuxiliaryWindowCoordinator],
        conversation_executor: SubmissionExecutor | None = None,
    ) -> None:
        super().__init__()
        self._agent_harness_service = agent_harness_service
        self._llm_service = llm_service
        self._artifact_service = artifact_service
        self._link_router = link_router
        self._current_locale = current_locale
        self._auxiliary_windows = auxiliary_factory(self)
        self._auxiliary_windows.settings_saved.connect(self._reload_agent_provider)
        self._conversation = ConversationTurnController()
        self._conversation_executor = conversation_executor or ThreadedSubmissionExecutor(
            self._agent_harness_service.submit_user_turn_stream
        )
        self._composer_attachments: dict[str, _ComposerAttachmentRecord] = {}
        self._submission_attachment_paths: tuple[str, ...] = ()
        self._service_link_progress_dialog: QProgressDialog | None = None
        self._active_service_link_activation_ids: set[str] = set()

        self._title_label = QLabel(parent=self)
        self._settings_button = QPushButton(parent=self)
        self._settings_button.clicked.connect(self._open_settings)
        self._knowledge_button = QPushButton(parent=self)
        self._knowledge_button.clicked.connect(self._open_knowledge_workspace)

        self._history_panel = HistoryPanel(
            history_port,
            is_thread_running=lambda thread_id: (
                self.conversation_thread_id == thread_id and not self.conversation_idle
            ),
            parent=self,
        )
        self._history_panel.thread_open_requested.connect(self._open_history_thread)
        self._history_panel.new_thread_requested.connect(self._create_agent_thread)
        self._history_panel.thread_deleted.connect(self._on_history_thread_deleted)
        self._assign_semantic_identities()

        self._thread_detail_view = ThreadDetailView(parent=self)
        self._thread_detail_view.set_artifact_resolver(self._artifact_service.resolve_uri)
        self._thread_detail_view.message_submitted.connect(self._submit_chat_message)
        self._thread_detail_view.files_attached.connect(self._register_source_attachments)
        self._thread_detail_view.attachment_removed.connect(self._discard_composer_attachment)
        self._thread_detail_view.model_selected.connect(self._update_thread_model)
        self._thread_detail_view.service_link_activated.connect(self._open_service_link)
        self._thread_detail_view.source_file_activated.connect(self._open_source_file)
        self._thread_detail_view.tool_action_requested.connect(self._handle_tool_action)
        self._thread_detail_view.stop_requested.connect(self._request_harness_stop)
        self._harness_failure_received.connect(self._render_harness_error)
        self._harness_stream_event.connect(self._render_harness_stream_event)
        self._service_link_activation_succeeded.connect(self._finish_service_link_activation)
        self._service_link_activation_failed.connect(self._fail_service_link_activation)

        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()
        self._sync_model_picker_options()

    @property
    def conversation_thread_id(self) -> str | None:
        return self._conversation.thread_id

    @property
    def conversation_idle(self) -> bool:
        return not self._conversation.busy

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
        self._knowledge_button.setMinimumWidth(112)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self._knowledge_button)
        header_layout.addWidget(self._settings_button)
        layout.addLayout(header_layout)

        content_layout = QHBoxLayout()
        content_layout.setObjectName("mainContentLayout")
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._history_panel)
        content_layout.addWidget(self._thread_detail_view, 1)
        layout.addLayout(content_layout, 1)

        self.setCentralWidget(root)
        self.refresh_history()
        first_thread_id = self._history_panel.first_thread_id
        if first_thread_id is not None:
            self._history_panel.open_thread(first_thread_id)
        dump_layout_if_enabled(root, reason="main-window-setup")

    def _assign_semantic_identities(self) -> None:
        identify(self._settings_button, "main.header.settings")
        identify(self._knowledge_button, "main.header.knowledge")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        super().closeEvent(event)
        if event.isAccepted():
            self._conversation.shutdown()
            self._conversation_executor.shutdown()
            self._history_panel.shutdown()
            self._auxiliary_windows.shutdown()
            self._active_service_link_activation_ids.clear()
            self._close_service_link_progress_if_idle()
            self.closing.emit()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Xenix Native"))
        self._title_label.setText(self.tr("Xenix"))
        self._settings_button.setText(self.tr("Settings"))
        self._knowledge_button.setText(self.tr("Knowledge"))
        self._history_panel.retranslate_ui()
        self._thread_detail_view.retranslate_ui()
        self._auxiliary_windows.retranslate_ui()
        self._retranslate_service_link_progress()
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
        if self.conversation_thread_id is not None:
            try:
                selected = self._agent_harness_service.get_thread_snapshot(
                    self.conversation_thread_id
                ).thread.selected_fq_model_key
            except Exception:
                selected = None
        self._thread_detail_view.set_model_options(
            options,
            selected_fq_model_key=selected or self._llm_service.default_fq_model_key(),
        )

    def _sync_thread_model_picker(self, snapshot: ConversationSnapshot) -> None:
        selected = snapshot.thread.selected_fq_model_key or self._llm_service.default_fq_model_key()
        self._thread_detail_view.set_selected_fq_model_key(selected)

    def _update_thread_model(self, fq_model_key: str) -> None:
        if self.conversation_thread_id is None:
            return
        try:
            snapshot = self._agent_harness_service.set_thread_model(self.conversation_thread_id, fq_model_key)
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))
            return
        self._sync_thread_model_picker(snapshot)

    def _open_settings(
        self,
        _checked: bool = False,
        *,
        tab: SettingsTab = SettingsTab.AI,
    ) -> None:
        self._auxiliary_windows.show_settings(tab=tab)

    def _open_knowledge_workspace(self) -> None:
        self._auxiliary_windows.show_knowledge()

    def _submit_chat_message(self, text: str, file_paths: list[str], fq_model_key: str) -> None:
        if not self.conversation_idle:
            return
        source_attachments = self._ready_source_attachments(file_paths)
        if source_attachments is None:
            return

        self._start_harness_submission(
            text=text,
            source_attachments=source_attachments,
            file_paths=file_paths,
            fq_model_key=fq_model_key,
            interface_locale=self._current_locale(),
            client_submission_id=uuid4().hex,
        )

    def _register_source_attachments(self, file_paths: list[str]) -> None:
        for file_path in file_paths:
            self._register_source_attachment(file_path)

    def _register_source_attachment(self, file_path: str) -> None:
        source_path = Path(file_path).expanduser().resolve()
        normalized_path = str(source_path)
        if normalized_path in self._composer_attachments:
            return
        self._thread_detail_view.set_attachment_status(
            normalized_path,
            ComposerAttachmentStatus.PENDING,
        )
        try:
            attachment = self._source_attachment_input(normalized_path)
        except Exception as exc:
            self._thread_detail_view.set_attachment_status(
                normalized_path,
                ComposerAttachmentStatus.FAILED,
                error=str(exc),
            )
            self._thread_detail_view.show_error(str(exc))
            return
        self._composer_attachments[normalized_path] = _ComposerAttachmentRecord(
            path=normalized_path,
            attachment=attachment,
        )
        self._thread_detail_view.set_attachment_status(
            normalized_path,
            ComposerAttachmentStatus.READY,
        )

    def _start_harness_submission(
        self,
        *,
        text: str,
        source_attachments: list[SourceAttachmentInput],
        file_paths: list[str],
        fq_model_key: str,
        interface_locale: str,
        client_submission_id: str,
    ) -> None:
        try:
            submit_input = SubmitUserTurnInput(
                thread_id=self.conversation_thread_id,
                text=text,
                source_attachments=source_attachments,
                fq_model_key=fq_model_key or None,
                interface_locale=interface_locale,
                client_submission_id=client_submission_id,
            )
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))
            return

        if not self._conversation.begin(client_submission_id, len(file_paths)):
            return
        self._submission_attachment_paths = tuple(str(Path(path).resolve()) for path in file_paths)
        self._thread_detail_view.begin_composer_submission(file_paths)
        try:
            self._conversation_executor.start(
                submit_input,
                on_event=self._harness_stream_event.emit,
                on_failure=self._harness_failure_received.emit,
            )
        except Exception as exc:
            self._render_harness_error(client_submission_id, exc)

    def _source_attachment_input(self, file_path: str) -> SourceAttachmentInput:
        source_path = Path(file_path).expanduser().resolve(strict=True)
        if not source_path.is_file():
            raise ValueError(self.tr("The selected source path is not a file."))
        return SourceAttachmentInput(file_path=str(source_path))

    def _ready_source_attachments(self, file_paths: list[str]) -> list[SourceAttachmentInput] | None:
        attachments: list[SourceAttachmentInput] = []
        for file_path in file_paths:
            record = self._composer_attachments.get(str(Path(file_path).resolve()))
            if record is None:
                return None
            attachments.append(record.attachment)
        return attachments

    def _discard_composer_attachment(self, file_path: str) -> None:
        self._composer_attachments.pop(str(Path(file_path).resolve()), None)

    @staticmethod
    def _open_source_file(file_path: str) -> None:
        """Open an ephemeral Chatbot source target without treating it as an Artifact."""

        try:
            source_path = Path(file_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            return
        if source_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(source_path)))

    def _render_harness_snapshot(self, snapshot: ConversationSnapshot) -> None:
        self._submission_attachment_paths = ()
        self._sync_thread_model_picker(snapshot)
        self._thread_detail_view.hide_thinking_indicator()
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))
        self._thread_detail_view.abort_composer_submission()
        self._thread_detail_view.set_running(False)
        self.refresh_history(selected_thread_id=snapshot.thread.id)

    def _render_harness_stream_event(self, event) -> None:
        update = self._conversation.route(event)
        if update.action is TurnAction.IGNORE:
            return
        if update.action is TurnAction.ATTACHMENT:
            if update.attachment_index is not None:
                self._render_attachment_import_progress(event, update.attachment_index)
            return
        if update.action is TurnAction.TITLE:
            self.refresh_history(selected_thread_id=self.conversation_thread_id)
            return
        if update.action is TurnAction.FINAL_SNAPSHOT:
            self._render_harness_snapshot(event.snapshot)
            return
        if update.action is TurnAction.SNAPSHOT:
            if update.acknowledge_composer:
                for file_path in self._submission_attachment_paths:
                    self._composer_attachments.pop(file_path, None)
                self._thread_detail_view.acknowledge_composer_submission()
            self._sync_thread_model_picker(event.snapshot)
            self._thread_detail_view.render_events(
                event.chatbot_events
                if event.chatbot_events is not None
                else self._agent_harness_service.project_chatbot_events(event.snapshot)
            )
            self.refresh_history(selected_thread_id=event.snapshot.thread.id)
            return
        if update.action is TurnAction.LIVE_EVENT:
            if update.activate_running:
                self._thread_detail_view.set_running(True)
            self._thread_detail_view.apply_chatbot_event(event.chatbot_event)

    def _render_harness_error(self, submission_id: str, failure: object) -> None:
        recovery = self._conversation.fail(submission_id)
        if recovery is FailureRecovery.IGNORE:
            return
        self._thread_detail_view.hide_thinking_indicator()
        if recovery is FailureRecovery.RESTORE_SNAPSHOT:
            self._restore_stable_message_view()
        self._submission_attachment_paths = ()
        self._thread_detail_view.abort_composer_submission()
        self._thread_detail_view.show_error(str(failure))
        self._thread_detail_view.set_running(False)
        self._harness_failed.emit(failure)

    def _render_attachment_import_progress(self, event: AgentHarnessStreamEvent, source_index: int) -> None:
        progress = event.attachment_import
        if progress is None:
            return
        path = self._submission_attachment_paths[source_index]
        if progress.status is AttachmentImportStatus.PENDING:
            self._thread_detail_view.set_attachment_status(path, ComposerAttachmentStatus.PENDING)
        elif progress.status is AttachmentImportStatus.FAILED:
            self._thread_detail_view.set_attachment_status(path, ComposerAttachmentStatus.FAILED)

    def _restore_stable_message_view(self) -> None:
        if self.conversation_thread_id is None:
            self._thread_detail_view.clear_messages()
            return
        try:
            snapshot = self._agent_harness_service.get_thread_snapshot(self.conversation_thread_id)
        except Exception:
            self._thread_detail_view.clear_messages()
            return
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))

    def _open_service_link(self, uri: str) -> None:
        activation_id = uuid4().hex
        thread_id = self.conversation_thread_id
        self._active_service_link_activation_ids.add(activation_id)
        self._show_service_link_progress()

        def run_activation() -> None:
            try:
                self._link_router.activate(uri, thread_id=thread_id)
            except Exception as exc:
                self._service_link_activation_failed.emit(
                    _ServiceLinkActivationFailed(
                        activation_id=activation_id,
                        uri=uri,
                        message=str(exc),
                    )
                )
                return
            self._service_link_activation_succeeded.emit(
                _ServiceLinkActivationSucceeded(
                    activation_id=activation_id,
                    uri=uri,
                )
            )

        threading.Thread(target=run_activation, name="xenix-service-link-activation", daemon=True).start()

    def _show_service_link_progress(self) -> None:
        if self._service_link_progress_dialog is not None:
            return
        dialog = QProgressDialog(
            self.tr("Opening link..."),
            "",
            0,
            0,
            self,
        )
        dialog.setObjectName("serviceLinkProgressDialog")
        dialog.setWindowModality(Qt.NonModal)
        dialog.setMinimumDuration(0)
        dialog.setCancelButton(None)
        self._service_link_progress_dialog = dialog
        self._retranslate_service_link_progress()
        dialog.show()

    def _retranslate_service_link_progress(self) -> None:
        if self._service_link_progress_dialog is None:
            return
        self._service_link_progress_dialog.setLabelText(self.tr("Opening link..."))
        self._service_link_progress_dialog.setWindowTitle(self.tr("Open Link"))

    def _close_service_link_progress_if_idle(self) -> None:
        if self._active_service_link_activation_ids or self._service_link_progress_dialog is None:
            return
        dialog = self._service_link_progress_dialog
        self._service_link_progress_dialog = None
        dialog.close()
        dialog.deleteLater()

    def _finish_service_link_activation(self, result: object) -> None:
        if not isinstance(result, _ServiceLinkActivationSucceeded):
            return
        self._active_service_link_activation_ids.discard(result.activation_id)
        self._close_service_link_progress_if_idle()

    def _fail_service_link_activation(self, result: object) -> None:
        if not isinstance(result, _ServiceLinkActivationFailed):
            return
        if result.activation_id not in self._active_service_link_activation_ids:
            return
        self._active_service_link_activation_ids.discard(result.activation_id)
        self._close_service_link_progress_if_idle()
        self._thread_detail_view.show_error(result.message)

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
        self._auxiliary_windows.show_tool_call_detail(task_ids=task_ids)

    def _request_harness_stop(self) -> None:
        disposition = self._conversation.stop_disposition()
        if disposition is StopDisposition.PREPARING:
            self._thread_detail_view.show_error(self.tr("The submitted message is being prepared and cannot be stopped."))
            return
        thread_id = self.conversation_thread_id
        if disposition is StopDisposition.NO_THREAD or thread_id is None:
            return
        try:
            self._agent_harness_service.pause_thread(thread_id)
        except Exception as exc:
            self._thread_detail_view.show_error(str(exc))
            return
        self._conversation.mark_paused(thread_id)
        self._thread_detail_view.hide_thinking_indicator()
        self._thread_detail_view.set_running(False)
        self._thread_detail_view.show_error(self.tr("Stopped."))

    def _reload_agent_provider(self) -> None:
        self._sync_model_picker_options()

    def _create_agent_thread(self) -> None:
        snapshot = self._agent_harness_service.create_thread(
            interface_locale=self._current_locale(),
        )
        self._select_conversation_thread(snapshot.thread.id)
        self._sync_thread_model_picker(snapshot)
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))
        self.refresh_history(selected_thread_id=snapshot.thread.id)

    def refresh_history(self, *, selected_thread_id: str | None = None) -> None:
        self._history_panel.refresh(selected_thread_id)

    def _open_history_thread(self, thread_id: str) -> None:
        snapshot = self._agent_harness_service.get_thread_snapshot(thread_id)
        self._select_conversation_thread(thread_id)
        self._sync_thread_model_picker(snapshot)
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))

    def _select_conversation_thread(self, thread_id: str | None) -> None:
        self._conversation.select_thread(thread_id)
        self._submission_attachment_paths = ()
        self._thread_detail_view.abort_composer_submission()
        self._thread_detail_view.set_running(False)

    def _on_history_thread_deleted(self, thread_id: str) -> None:
        if self.conversation_thread_id != thread_id:
            self.refresh_history(selected_thread_id=self.conversation_thread_id)
            return
        self._select_conversation_thread(None)
        self._thread_detail_view.clear_messages()
        self.refresh_history()
        first_thread_id = self._history_panel.first_thread_id
        if first_thread_id is not None:
            self._history_panel.open_thread(first_thread_id)
