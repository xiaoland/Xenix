"""Chat workspace orchestration between conversation services and widgets.

``ChatWorkspace`` connects the conversation services to the ``HistoryPanel`` and
``ThreadDetailView`` widgets.  ``MainWindow`` owns the window shell, the main-area
layout, top-level navigation, and the widget lifecycle; this ``QObject`` owns the
UI-local turn controller, the submission executor, source-attachment records,
model-picker sync, and the stream/error/service-link marshaling.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QDialog, QMessageBox, QProgressDialog

from ..exceptions import XenixError, report_exception
from ..services.agent.harness_service import (
    AgentHarnessService,
    AgentHarnessStreamEvent,
    AttachmentImportStatus,
    SourceAttachmentInput,
    SubmitUserTurnInput,
)
from ..services.artifact_service import ArtifactService
from ..services.link_router import LinkRouter
from ..services.llm import ConversationSnapshot, LLMService
from ..services.llm.conversation_models import UserMessageReplacement
from .chatbot import ComposerAttachmentStatus, ThreadDetailView
from .conversation.clipboard import message_clipboard
from .conversation.execution import SubmissionExecutor, ThreadedSubmissionExecutor
from .conversation.message_editor import UserMessageEditor
from .conversation.queue_panel import QueuedMessage
from .conversation.turn_controller import (
    ConversationTurnController,
    FailureRecovery,
    StopDisposition,
    TurnAction,
    TurnUpdate,
)
from .history import HistoryPanel


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


@dataclass
class _Submission:
    input: SubmitUserTurnInput
    steering: bool = False
    holding_draft: bool = False
    failure: str = ""

    @property
    def paths(self) -> list[str]:
        return [source.file_path for source in self.input.source_attachments]

    @property
    def edit_message_id(self) -> int | None:
        return self.input.replacement.message_id if self.input.replacement is not None else None


@dataclass
class _ThreadInput:
    controller: ConversationTurnController = field(default_factory=ConversationTurnController)
    waiting: list[_Submission] = field(default_factory=list)
    active: _Submission | None = None
    steer_requested: threading.Event = field(default_factory=threading.Event)
    paused: bool = False


class ChatWorkspace(QObject):
    """Own conversation orchestration; never the window shell or widget layout."""

    harness_stream_event = Signal(object)
    harness_failed = Signal(object)
    _harness_failure_received = Signal(str, object)
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
        history_panel: HistoryPanel,
        thread_detail_view: ThreadDetailView,
        conversation_executor: SubmissionExecutor | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._agent_harness_service = agent_harness_service
        self._llm_service = llm_service
        self._artifact_service = artifact_service
        self._link_router = link_router
        self._current_locale = current_locale
        self._history_panel = history_panel
        self._thread_detail_view = thread_detail_view
        self._lane = _ThreadInput()
        self._by_thread: dict[int, _ThreadInput] = {}
        self._by_submission: dict[str, _ThreadInput] = {}
        self._closed = False
        self._conversation_executor = conversation_executor or ThreadedSubmissionExecutor(self._submission_stream)
        self._composer_attachments: dict[str, _ComposerAttachmentRecord] = {}
        self._service_link_progress_dialog: QProgressDialog | None = None
        self._active_service_link_activation_ids: set[str] = set()

        self._thread_detail_view.set_artifact_resolver(self._artifact_service.resolve_uri)
        self._thread_detail_view.message_submitted.connect(self._submit_chat_message)
        self._thread_detail_view.steering_submitted.connect(self._steer_chat_message)
        self._thread_detail_view.message_edit_requested.connect(self._edit_message)
        self._thread_detail_view.message_copy_requested.connect(self._copy_message)
        self._thread_detail_view.message_queue.remove_requested.connect(self._remove_queued_message)
        self._thread_detail_view.message_queue.restore_requested.connect(self._restore_queued_message)
        self._thread_detail_view.message_queue.resume_requested.connect(self._resume_queue)
        self._thread_detail_view.files_attached.connect(self._register_source_attachments)
        self._thread_detail_view.attachment_removed.connect(self._discard_composer_attachment)
        self._thread_detail_view.model_selected.connect(self._update_thread_model)
        self._thread_detail_view.service_link_activated.connect(self._open_service_link)
        self._thread_detail_view.source_file_activated.connect(self._open_source_file)
        self._thread_detail_view.stop_requested.connect(self._request_harness_stop)
        self._history_panel.thread_open_requested.connect(self._open_history_thread)
        self._history_panel.new_thread_requested.connect(self._create_agent_thread)
        self._history_panel.thread_deleted.connect(self._on_history_thread_deleted)
        self._harness_failure_received.connect(self._render_harness_error)
        self.harness_stream_event.connect(self._render_harness_stream_event)
        self._service_link_activation_succeeded.connect(self._finish_service_link_activation)
        self._service_link_activation_failed.connect(self._fail_service_link_activation)

    # Public shell surface ---------------------------------------------------

    @property
    def conversation_thread_id(self) -> int | None:
        return self._lane.controller.thread_id

    @property
    def conversation_idle(self) -> bool:
        return self._lane.active is None

    def thread_has_input_work(self, thread_id: int) -> bool:
        lane = self._by_thread.get(thread_id)
        return lane is not None and (lane.active is not None or bool(lane.waiting))

    @property
    def composer_attachments(self) -> dict[str, _ComposerAttachmentRecord]:
        return self._composer_attachments

    def refresh_history(self, *, selected_thread_id: int | None = None) -> None:
        self._history_panel.refresh(selected_thread_id)

    def open_initial_thread(self) -> None:
        self.refresh_history()
        first_thread_id = self._history_panel.first_thread_id
        if first_thread_id is not None:
            self._history_panel.open_thread(first_thread_id)

    def sync_model_options(self) -> None:
        options = [(option.fq_model_key, option.label) for option in self._llm_service.model_options()]
        selected: str | None = None
        if self.conversation_thread_id is not None:
            try:
                selected = self._agent_harness_service.get_thread_snapshot(
                    self.conversation_thread_id
                ).thread.selected_fq_model_key
            except Exception as exc:
                report_exception(exc)
                selected = None
        else:
            selected = self._thread_detail_view.selected_fq_model_key() or None
        if not any(key == selected for key, _ in options):
            selected = self._llm_service.default_fq_model_key()
        self._thread_detail_view.set_model_options(options, selected_fq_model_key=selected)

    def retranslate_ui(self) -> None:
        self._retranslate_service_link_progress()
        self.sync_model_options()

    def shutdown(self) -> None:
        self._closed = True
        for lane in self._by_thread.values():
            lane.controller.shutdown()
        self._lane.controller.shutdown()
        self._conversation_executor.shutdown()
        self._by_submission.clear()
        self._by_thread.clear()
        self._lane.active = None
        self._lane.waiting.clear()
        self._active_service_link_activation_ids.clear()
        self._close_service_link_progress_if_idle()

    # Model picker -----------------------------------------------------------

    def _sync_thread_model_picker(self, snapshot: ConversationSnapshot) -> None:
        if not self._thread_detail_view.set_selected_fq_model_key(snapshot.thread.selected_fq_model_key):
            self._thread_detail_view.set_selected_fq_model_key(self._llm_service.default_fq_model_key())

    def _update_thread_model(self, fq_model_key: str) -> None:
        if self.conversation_thread_id is None or not self.conversation_idle:
            return
        try:
            snapshot = self._agent_harness_service.set_thread_model(self.conversation_thread_id, fq_model_key)
        except Exception as exc:
            if not isinstance(exc, XenixError):
                report_exception(exc)
            self._thread_detail_view.show_operation_error(str(exc))
            try:
                current = self._agent_harness_service.get_thread_snapshot(self.conversation_thread_id)
            except Exception:
                self.sync_model_options()
            else:
                self._sync_thread_model_picker(current)
            return
        self._sync_thread_model_picker(snapshot)

    # Submission and source attachments --------------------------------------

    def _submit_chat_message(self, text: str, file_paths: list[str], fq_model_key: str) -> None:
        self._accept_message(text, file_paths, fq_model_key, steer=False)

    def _steer_chat_message(self, text: str, file_paths: list[str], fq_model_key: str) -> None:
        self._accept_message(text, file_paths, fq_model_key, steer=True)

    def _accept_message(self, text: str, file_paths: list[str], fq_model_key: str, *, steer: bool) -> None:
        source_attachments = self._ready_source_attachments(file_paths)
        if source_attachments is None:
            return
        entry = _Submission(SubmitUserTurnInput(
            thread_id=self.conversation_thread_id,
            text=text,
            source_attachments=source_attachments,
            fq_model_key=fq_model_key or None,
            interface_locale=self._current_locale(),
            client_submission_id=uuid4().hex,
        ), steering=steer)
        self._thread_detail_view.clear_operation_notification()
        self._lane.paused = False
        if self.conversation_idle and not any(not item.failure for item in self._lane.waiting):
            entry.holding_draft = True
            self._start_submission(self._lane, entry)
            return
        self._clear_submitted_draft(entry)
        self._enqueue(self._lane, entry)

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
            if not isinstance(exc, XenixError):
                report_exception(exc)
            self._thread_detail_view.set_attachment_status(
                normalized_path,
                ComposerAttachmentStatus.FAILED,
                error=str(exc),
            )
            self._thread_detail_view.show_operation_error(str(exc))
            return
        self._composer_attachments[normalized_path] = _ComposerAttachmentRecord(
            path=normalized_path,
            attachment=attachment,
        )
        self._thread_detail_view.set_attachment_status(
            normalized_path,
            ComposerAttachmentStatus.READY,
        )

    def _submission_stream(self, submission: SubmitUserTurnInput) -> Iterable[AgentHarnessStreamEvent]:
        lane = self._by_submission.get(submission.client_submission_id or "")
        return self._agent_harness_service.submit_user_turn_stream(
            submission, should_steer=lane.steer_requested.is_set if lane is not None else None,
        )

    def _start_submission(self, lane: _ThreadInput, entry: _Submission) -> None:
        submission_id = entry.input.client_submission_id
        assert submission_id is not None
        if not lane.controller.begin(submission_id, len(entry.paths)):
            return
        lane.active = entry
        self._by_submission[submission_id] = lane
        entry.input.thread_id = lane.controller.thread_id
        if lane is self._lane:
            if entry.holding_draft:
                self._thread_detail_view.begin_composer_submission(entry.paths)
            else:
                self._thread_detail_view.set_running(True)
        try:
            self._conversation_executor.start(
                entry.input,
                on_event=self.harness_stream_event.emit,
                on_failure=self._harness_failure_received.emit,
            )
        except Exception as exc:
            self._render_harness_error(submission_id, exc)

    def _enqueue(self, lane: _ThreadInput, entry: _Submission) -> None:
        index = next(
            (
                i for i, item in enumerate(lane.waiting)
                if item.edit_message_id is None and (entry.edit_message_id is not None or entry.steering and not item.steering)
            ),
            len(lane.waiting),
        )
        lane.waiting.insert(index, entry)
        self._update_steering(lane)
        self._render_queue()
        self._drain_queue(lane)

    @staticmethod
    def _update_steering(lane: _ThreadInput) -> None:
        if not lane.paused and any(item.steering and not item.failure for item in lane.waiting):
            lane.steer_requested.set()
        else:
            lane.steer_requested.clear()

    def _drain_queue(self, lane: _ThreadInput) -> None:
        if self._closed or lane.paused or lane.active is not None:
            return
        while (entry := next((item for item in lane.waiting if not item.failure), None)) is not None:
            if entry.edit_message_id is not None and lane is not self._lane:
                # The history confirmation belongs to the owning Thread view.
                return
            lane.waiting.remove(entry)
            self._update_steering(lane)
            self._render_queue()
            if entry.edit_message_id is not None:
                # The modal dialog may process Qt callbacks. Keep this lane
                # occupied until its freshly observed suffix is confirmed.
                lane.active = entry
                try:
                    accepted = self._prepare_edit(lane, entry)
                finally:
                    lane.active = None
                if not accepted:
                    continue
            self._start_submission(lane, entry)
            return

    def _render_queue(self) -> None:
        self._thread_detail_view.message_queue.set_messages(tuple(
            QueuedMessage(
                entry.input.client_submission_id or "", entry.input.text, len(entry.paths),
                entry.steering, entry.edit_message_id is not None, entry.failure,
            )
            for entry in self._lane.waiting
        ), paused=self._lane.paused)

    def _remove_queued_message(self, submission_id: str) -> None:
        self._lane.waiting = [
            entry for entry in self._lane.waiting if entry.input.client_submission_id != submission_id
        ]
        self._update_steering(self._lane)
        self._render_queue()

    def _restore_queued_message(self, submission_id: str) -> None:
        entry = next((item for item in self._lane.waiting if item.input.client_submission_id == submission_id), None)
        if entry is None or entry.edit_message_id is not None:
            return
        editor = self._thread_detail_view.composer.editor
        if not editor.isEnabled():
            return
        if entry.input.text:
            if editor.toPlainText():
                editor.appendPlainText(entry.input.text)
            else:
                editor.setPlainText(entry.input.text)
        self._thread_detail_view.composer.add_local_files(entry.paths)
        self._remove_queued_message(submission_id)
        editor.setFocus()

    def _resume_queue(self) -> None:
        self._lane.paused = False
        self._update_steering(self._lane)
        self._render_queue()
        self._drain_queue(self._lane)

    def _clear_submitted_draft(self, entry: _Submission) -> None:
        for path in entry.paths:
            self._composer_attachments.pop(path, None)
        self._thread_detail_view.acknowledge_composer_submission()

    def _copy_message(self, message_id: int) -> None:
        thread_id = self.conversation_thread_id
        if thread_id is None:
            return
        try:
            draft = self._agent_harness_service.message_draft(thread_id, message_id)
        except XenixError as exc:
            self._thread_detail_view.show_operation_error(str(exc))
            return
        QGuiApplication.clipboard().setMimeData(message_clipboard(draft.text, draft.paths))
        if any(attachment.path is None for attachment in draft.attachments):
            self._thread_detail_view.show_operation_status(self.tr("Some attachment paths are unavailable."))

    def _edit_message(self, message_id: int) -> None:
        lane = self._lane
        thread_id = lane.controller.thread_id
        if thread_id is None:
            return
        try:
            draft = self._agent_harness_service.message_draft(thread_id, message_id)
        except XenixError as exc:
            self._thread_detail_view.show_operation_error(str(exc))
            return
        editor = UserMessageEditor(draft, self._thread_detail_view)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        dataset_ids, paths = editor.attachments()
        try:
            entry = _Submission(SubmitUserTurnInput(
                thread_id=thread_id,
                text=editor.editor.toPlainText().strip(),
                source_attachments=[self._source_attachment_input(path) for path in paths],
                fq_model_key=self._thread_detail_view.selected_fq_model_key() or None,
                interface_locale=self._current_locale(),
                client_submission_id=uuid4().hex,
                replacement=UserMessageReplacement(message_id=message_id, retained_dataset_ids=dataset_ids),
            ))
        except (OSError, ValueError) as exc:
            self._thread_detail_view.show_operation_error(str(exc))
            return
        self._thread_detail_view.clear_operation_notification()
        lane.paused = False
        self._enqueue(lane, entry)

    def _prepare_edit(self, lane: _ThreadInput, entry: _Submission) -> bool:
        thread_id = lane.controller.thread_id
        replacement = entry.input.replacement
        assert thread_id is not None and replacement is not None
        try:
            draft = self._agent_harness_service.message_draft(thread_id, replacement.message_id)
        except XenixError as exc:
            self._thread_detail_view.show_operation_error(str(exc))
            return False
        following = draft.following_ids
        if following and QMessageBox.question(
            self._thread_detail_view,
            self.tr("Replace this message?"),
            self.tr("Saving will remove %n later conversation record(s) and send the edited message.", "", len(following)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return False
        entry.input.replacement = replacement.model_copy(update={"confirmed_following_ids": following})
        return True

    def _source_attachment_input(self, file_path: str) -> SourceAttachmentInput:
        source_path = Path(file_path).expanduser().resolve(strict=True)
        if not source_path.is_file():
            raise ValueError(QCoreApplication.translate("MainWindow", "The selected source path is not a file."))
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
        except OSError, RuntimeError:
            return
        if source_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(source_path)))

    # Stream and error rendering ---------------------------------------------

    def _render_harness_stream_event(self, event: AgentHarnessStreamEvent) -> None:
        if self._closed:
            return
        if event.kind == "title":
            if event.thread_id == self.conversation_thread_id:
                self.refresh_history(selected_thread_id=self.conversation_thread_id)
            return
        submission_id = event.client_submission_id or ""
        lane = self._by_submission.get(submission_id)
        if lane is None or lane.active is None:
            return
        entry = lane.active
        previous_thread_id = lane.controller.thread_id
        update = lane.controller.route(event)
        if update.action is TurnAction.IGNORE:
            return
        if event.thread_id is not None:
            self._by_thread[event.thread_id] = lane
        if lane is self._lane:
            if previous_thread_id is None and update.action is TurnAction.ATTACHMENT:
                self.conversation_changed.emit(lane.controller.thread_id)
            self._render_active_event(event, update, entry)

        if update.acknowledge_composer:
            entry.holding_draft = False
        if update.action is TurnAction.FINAL_SNAPSHOT:
            self._finish_submission(lane, submission_id)

    def _render_active_event(
        self, event: AgentHarnessStreamEvent, update: TurnUpdate, entry: _Submission,
    ) -> None:
        if update.action is TurnAction.ATTACHMENT:
            if update.attachment_index is not None and entry.holding_draft and event.attachment_import is not None:
                path = entry.paths[update.attachment_index]
                status = (
                    ComposerAttachmentStatus.PENDING if event.attachment_import.status is AttachmentImportStatus.PENDING
                    else ComposerAttachmentStatus.FAILED
                )
                self._thread_detail_view.set_attachment_status(path, status)
            return
        if update.action in {TurnAction.SNAPSHOT, TurnAction.FINAL_SNAPSHOT}:
            assert event.snapshot is not None
            if (update.acknowledge_composer or update.action is TurnAction.FINAL_SNAPSHOT) and entry.holding_draft:
                self._clear_submitted_draft(entry)
                self._thread_detail_view.abort_composer_submission()
            if update.acknowledge_composer:
                self._thread_detail_view.set_running(True)
            self._thread_detail_view.render_events(
                event.chatbot_events
                if event.chatbot_events is not None
                else self._agent_harness_service.project_chatbot_events(event.snapshot)
            )
            if update.action is TurnAction.FINAL_SNAPSHOT:
                self._thread_detail_view.set_running(False)
            self.conversation_changed.emit(event.snapshot.thread.id)
            self.refresh_history(selected_thread_id=event.snapshot.thread.id)
            return
        if update.activate_running:
            self._thread_detail_view.set_running(True)
        self._thread_detail_view.apply_chatbot_event(event.chatbot_event)

    def _render_harness_error(self, submission_id: str, failure: object) -> None:
        lane = self._by_submission.get(submission_id)
        if lane is None or lane.active is None:
            return
        entry = lane.active
        recovery = lane.controller.fail(submission_id)
        if recovery is FailureRecovery.IGNORE:
            return
        if recovery is FailureRecovery.PRESERVE_COMPOSER and not entry.holding_draft:
            entry.failure = str(failure)
            lane.waiting.append(entry)
        if lane is self._lane:
            self._thread_detail_view.hide_thinking_indicator()
            if recovery is FailureRecovery.RESTORE_SNAPSHOT:
                self._restore_stable_message_view()
            self._thread_detail_view.abort_composer_submission()
            self._thread_detail_view.show_submission_error(str(failure))
            self._thread_detail_view.set_running(False)
            self.harness_failed.emit(failure)
        if isinstance(failure, Exception) and not isinstance(failure, XenixError):
            report_exception(failure)
        self._finish_submission(lane, submission_id)

    def _finish_submission(self, lane: _ThreadInput, submission_id: str) -> None:
        self._by_submission.pop(submission_id, None)
        lane.active = None
        self._update_steering(lane)
        self._render_queue()
        self._drain_queue(lane)

    def _restore_stable_message_view(self) -> None:
        if self.conversation_thread_id is None:
            self._thread_detail_view.clear_messages()
            return
        try:
            snapshot = self._agent_harness_service.get_thread_snapshot(self.conversation_thread_id)
        except Exception as exc:
            report_exception(exc)
            self._thread_detail_view.clear_messages()
            return
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))

    # Service link activation ------------------------------------------------

    def _open_service_link(self, uri: str) -> None:
        activation_id = uuid4().hex
        thread_id = self.conversation_thread_id
        self._active_service_link_activation_ids.add(activation_id)
        self._show_service_link_progress()

        def run_activation() -> None:
            try:
                self._link_router.activate(uri, thread_id=thread_id)
            except Exception as exc:
                if not isinstance(exc, XenixError):
                    report_exception(exc)
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
            QCoreApplication.translate("MainWindow", "Opening link..."),
            "",
            0,
            0,
            self._thread_detail_view,
        )
        dialog.setObjectName("serviceLinkProgressDialog")
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setMinimumDuration(0)
        dialog.setCancelButton(None)
        self._service_link_progress_dialog = dialog
        self._retranslate_service_link_progress()
        dialog.show()

    def _retranslate_service_link_progress(self) -> None:
        if self._service_link_progress_dialog is None:
            return
        self._service_link_progress_dialog.setLabelText(QCoreApplication.translate("MainWindow", "Opening link..."))
        self._service_link_progress_dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "Open Link"))

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
        self._thread_detail_view.show_operation_error(result.message)

    # Tool actions and stop --------------------------------------------------

    def open_thread(self, thread_id: int) -> None:
        try:
            self._open_history_thread(thread_id)
        except XenixError as exc:
            self._thread_detail_view.show_operation_error(str(exc))

    def open_artifact(self, uri: str) -> None:
        self._open_service_link(uri)

    def _request_harness_stop(self) -> None:
        disposition = self._lane.controller.stop_disposition()
        if disposition is StopDisposition.PREPARING:
            self._thread_detail_view.show_operation_error(
                QCoreApplication.translate(
                    "MainWindow", "The submitted message is being prepared and cannot be stopped."
                )
            )
            return
        thread_id = self.conversation_thread_id
        if disposition is StopDisposition.NO_THREAD or thread_id is None:
            return
        try:
            self._agent_harness_service.pause_thread(thread_id)
        except Exception as exc:
            if not isinstance(exc, XenixError):
                report_exception(exc)
            self._thread_detail_view.show_operation_error(str(exc))
            return
        self._lane.controller.mark_paused(thread_id)
        self._lane.paused = True
        self._update_steering(self._lane)
        self._render_queue()
        self._thread_detail_view.hide_thinking_indicator()
        self._thread_detail_view.set_running(False)
        self._thread_detail_view.show_operation_status(QCoreApplication.translate("MainWindow", "Stopped."))

    # Thread lifecycle -------------------------------------------------------

    def _create_agent_thread(self) -> None:
        snapshot = self._agent_harness_service.create_thread(
            interface_locale=self._current_locale(),
        )
        self._select_conversation_thread(snapshot.thread.id)
        self._sync_thread_model_picker(snapshot)
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))
        self.refresh_history(selected_thread_id=snapshot.thread.id)

    def _open_history_thread(self, thread_id: int) -> None:
        snapshot = self._agent_harness_service.get_thread_snapshot(thread_id)
        self._select_conversation_thread(thread_id)
        self._sync_thread_model_picker(snapshot)
        self._thread_detail_view.render_events(self._agent_harness_service.project_chatbot_events(snapshot))
        self._drain_queue(self._lane)

    conversation_changed = Signal(object)

    def _select_conversation_thread(self, thread_id: int | None) -> None:
        previous = self._lane
        lane = self._by_thread.get(thread_id) if thread_id is not None else None
        if lane is None:
            lane = _ThreadInput()
            if thread_id is not None:
                lane.controller.select_thread(thread_id)
                self._by_thread[thread_id] = lane
        if previous is not lane and previous.active is not None:
            previous.active.holding_draft = False
        self._lane = lane
        self.conversation_changed.emit(thread_id)
        self._thread_detail_view.clear_operation_notification()
        if lane.active is None or not lane.active.holding_draft:
            self._thread_detail_view.abort_composer_submission()
            self._thread_detail_view.set_running(lane.active is not None and not lane.paused)
        self._render_queue()

    def _on_history_thread_deleted(self, thread_id: int) -> None:
        self._by_thread.pop(thread_id, None)
        if self.conversation_thread_id != thread_id:
            self.refresh_history(selected_thread_id=self.conversation_thread_id)
            return
        self._select_conversation_thread(None)
        self._thread_detail_view.clear_messages()
        self.refresh_history()
        first_thread_id = self._history_panel.first_thread_id
        if first_thread_id is not None:
            self._history_panel.open_thread(first_thread_id)
