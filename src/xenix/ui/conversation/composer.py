"""Chat composer: input, attachments, and submission intent.

``ChatComposer`` owns the composer state machine (draft text, attachment set and
their per-file status, running/preparing/step-confirmation flags, model choice)
and emits intents as signals.  It never reaches into the timeline or the shell.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..icons import attach_file_icon, spinner_icon
from ..semantic_identity import identify
from .presentation import (
    ComposerAttachmentState,
    ComposerAttachmentStatus,
    SUPPORTED_DATASET_SUFFIXES,
)
from .widgets import AttachmentChip, AutoGrowingTextEdit


class ChatComposer(QWidget):
    message_submitted = Signal(str, list, str)
    files_attached = Signal(list)
    attachment_removed = Signal(str)
    stop_requested = Signal()
    step_budget_continue_requested = Signal()
    step_budget_stop_requested = Signal()
    model_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._attached_files: list[str] = []
        self._attachment_states: dict[str, ComposerAttachmentState] = {}
        self._running = False
        self._preparing_submission = False
        self._awaiting_step_confirmation = False
        self._model_options: list[tuple[str, str]] = []
        self.setAcceptDrops(True)

        self._composer = QFrame()
        self._composer.setObjectName("chatComposer")
        self._composer.setFrameShape(QFrame.StyledPanel)
        composer_layout = QVBoxLayout(self._composer)
        composer_layout.setObjectName("chatComposerLayout")
        composer_layout.setContentsMargins(10, 8, 10, 8)
        composer_layout.setSpacing(7)

        self._attachment_bar = QWidget()
        self._attachment_bar.setObjectName("chatAttachmentBar")
        self._attachment_layout = QHBoxLayout(self._attachment_bar)
        self._attachment_layout.setObjectName("chatAttachmentLayout")
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(6)
        self._attachment_layout.addStretch(1)

        self._attach_button = QPushButton()
        self._configure_attach_button(self._attach_button)
        self._attach_button.clicked.connect(self._choose_files)

        self._editor = AutoGrowingTextEdit(max_lines=6)
        self._editor.setObjectName("chatComposerEditor")
        self._editor.submit_requested.connect(self._handle_button_clicked)

        self._model_picker = QComboBox()
        self._model_picker.setObjectName("modelPicker")
        self._model_picker.setMinimumWidth(180)
        self._model_picker.setFixedHeight(34)
        self._model_picker.currentIndexChanged.connect(self._handle_model_picker_changed)

        self._send_button = QPushButton()
        self._send_button.setObjectName("sendButton")
        self._send_button.setMinimumWidth(76)
        self._send_button.setFixedHeight(34)
        self._send_button.clicked.connect(self._handle_button_clicked)

        self._step_confirmation_bar = QFrame()
        self._step_confirmation_bar.setObjectName("stepConfirmationBar")
        self._step_confirmation_bar.setFrameShape(QFrame.StyledPanel)
        step_confirmation_layout = QHBoxLayout(self._step_confirmation_bar)
        step_confirmation_layout.setContentsMargins(10, 8, 10, 8)
        step_confirmation_layout.setSpacing(8)

        self._step_confirmation_label = QLabel()
        self._step_confirmation_label.setObjectName("stepConfirmationLabel")
        self._step_confirmation_label.setWordWrap(True)

        self._step_continue_button = QPushButton()
        self._step_continue_button.setObjectName("stepContinueButton")
        self._step_continue_button.clicked.connect(self.step_budget_continue_requested.emit)

        self._step_stop_button = QPushButton()
        self._step_stop_button.setObjectName("stepStopButton")
        self._step_stop_button.clicked.connect(self.step_budget_stop_requested.emit)
        self._assign_semantic_identities()

        step_confirmation_layout.addWidget(self._step_confirmation_label, 1)
        step_confirmation_layout.addWidget(self._step_continue_button, 0, Qt.AlignVCenter)
        step_confirmation_layout.addWidget(self._step_stop_button, 0, Qt.AlignVCenter)
        self._step_confirmation_bar.hide()

        self._composer_controls_row = QHBoxLayout()
        self._composer_controls_row.setObjectName("chatComposerControlsRow")
        self._composer_controls_row.setContentsMargins(0, 0, 0, 0)
        self._composer_controls_row.setSpacing(8)
        self._composer_controls_row.addWidget(self._attach_button)
        self._composer_controls_row.addStretch(1)
        self._composer_controls_row.addWidget(self._model_picker)
        self._composer_controls_row.addWidget(self._send_button)

        composer_layout.addWidget(self._step_confirmation_bar)
        composer_layout.addWidget(self._attachment_bar)
        composer_layout.addWidget(self._editor)
        composer_layout.addLayout(self._composer_controls_row)

        self._composer_shell = QWidget()
        self._composer_shell.setObjectName("chatComposerShell")
        composer_shell_layout = QHBoxLayout(self._composer_shell)
        composer_shell_layout.setObjectName("chatComposerShellLayout")
        composer_shell_layout.setContentsMargins(0, 0, 0, 0)
        composer_shell_layout.setSpacing(0)
        composer_shell_layout.addWidget(self._composer, 1)

        self._composer_drop_overlay = QFrame(self._composer_shell)
        self._composer_drop_overlay.setObjectName("composerDropOverlay")
        self._composer_drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._composer_drop_overlay.setAutoFillBackground(True)
        self._composer_drop_overlay.setFrameShape(QFrame.StyledPanel)
        self._composer_drop_overlay.setFrameShadow(QFrame.Raised)
        composer_drop_layout = QVBoxLayout(self._composer_drop_overlay)
        composer_drop_layout.setContentsMargins(12, 10, 12, 10)
        composer_drop_layout.setSpacing(3)
        composer_drop_layout.setAlignment(Qt.AlignCenter)

        self._composer_drop_title = QLabel()
        self._composer_drop_title.setObjectName("composerDropTitle")
        self._composer_drop_title.setAlignment(Qt.AlignCenter)
        composer_drop_title_font = QFont(self._composer_drop_title.font())
        composer_drop_title_font.setBold(True)
        self._composer_drop_title.setFont(composer_drop_title_font)

        self._composer_drop_hint = QLabel()
        self._composer_drop_hint.setObjectName("composerDropHint")
        self._composer_drop_hint.setAlignment(Qt.AlignCenter)

        composer_drop_layout.addWidget(self._composer_drop_title)
        composer_drop_layout.addWidget(self._composer_drop_hint)
        self._composer_drop_overlay.hide()
        self._install_composer_drop_filters()

        root = QVBoxLayout(self)
        root.setObjectName("chatComposerRootLayout")
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._composer_shell, 0)

        self.retranslate_ui()
        self._refresh_attachment_chips()
        self._sync_composer_drop_overlay_geometry()

    def _assign_semantic_identities(self) -> None:
        identify(self._attach_button, "chat.composer.attach-files")
        identify(self._editor, "chat.composer.editor")
        identify(self._model_picker, "chat.composer.model-picker")
        identify(self._send_button, "chat.composer.send-or-stop")
        identify(self._step_continue_button, "chat.step-budget.continue")
        identify(self._step_stop_button, "chat.step-budget.stop")

    def retranslate_ui(self) -> None:
        self._editor.setPlaceholderText(self.tr("Message Xenix"))
        self._editor.setAccessibleName(self.tr("Message Xenix"))
        self._attach_button.setToolTip(self.tr("Attach files"))
        self._attach_button.setAccessibleName(self.tr("Attach files"))
        self._model_picker.setToolTip(self.tr("Model for the next turn"))
        self._model_picker.setAccessibleName(self.tr("Model for the next turn"))
        self._step_continue_button.setText(self.tr("Continue"))
        self._step_stop_button.setText(self.tr("Stop"))
        self._composer_drop_title.setText(self.tr("Drop files to attach"))
        self._composer_drop_hint.setText(self.tr("Release here to add them to the next message"))
        self._sync_send_button_text()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self._preparing_submission = False
            self._set_composer_drop_hover(False)
            self.clear_step_confirmation()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def begin_composer_submission(self, attachment_paths: list[str]) -> None:
        """Lock the captured Composer input while Harness owns its import."""

        self._preparing_submission = True
        self._set_composer_drop_hover(False)
        for raw_path in attachment_paths:
            path = str(Path(raw_path).resolve())
            state = self._attachment_states.get(path)
            if state is not None:
                state.status = ComposerAttachmentStatus.PENDING
                state.error = None
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def acknowledge_composer_submission(self) -> None:
        """Drop only input that has already become a canonical UserMessage."""

        self._editor.clear()
        self._attached_files.clear()
        self._attachment_states.clear()
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def abort_composer_submission(self) -> None:
        """Return a pre-append Composer to an editable, retryable state."""

        self._preparing_submission = False
        for state in self._attachment_states.values():
            if state.status is ComposerAttachmentStatus.PENDING:
                state.status = ComposerAttachmentStatus.READY
                state.error = None
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def set_model_options(
        self,
        options: list[tuple[str, str]],
        *,
        selected_fq_model_key: str | None = None,
    ) -> None:
        self._model_options = list(options)
        current_key = selected_fq_model_key or self.selected_fq_model_key()
        self._model_picker.blockSignals(True)
        self._model_picker.clear()
        for fq_model_key, label in self._model_options:
            self._model_picker.addItem(label, fq_model_key)
        if current_key:
            index = self._model_picker.findData(current_key)
            if index >= 0:
                self._model_picker.setCurrentIndex(index)
        self._model_picker.blockSignals(False)
        self._sync_composer_controls_enabled()

    def set_selected_fq_model_key(self, fq_model_key: str | None) -> None:
        if not fq_model_key:
            return
        index = self._model_picker.findData(fq_model_key)
        if index < 0:
            return
        self._model_picker.blockSignals(True)
        self._model_picker.setCurrentIndex(index)
        self._model_picker.blockSignals(False)

    def selected_fq_model_key(self) -> str:
        value = self._model_picker.currentData()
        return str(value or "")

    def _handle_model_picker_changed(self, _index: int) -> None:
        fq_model_key = self.selected_fq_model_key()
        if fq_model_key:
            self.model_selected.emit(fq_model_key)

    def _sync_send_button_text(self) -> None:
        self._send_button.setIcon(QIcon())
        if self._running:
            send_text = self.tr("Stop")
        elif self._preparing_submission:
            send_text = self.tr("Send")
        elif self._has_pending_attachments():
            send_text = ""
            self._send_button.setIcon(spinner_icon())
            self._send_button.setIconSize(QSize(16, 16))
        else:
            send_text = self.tr("Send")
        self._send_button.setText(send_text)
        if self._running:
            accessible_name = self.tr("Stop")
        elif self._has_pending_attachments():
            accessible_name = self.tr("Preparing attachments")
        else:
            accessible_name = self.tr("Send")
        self._send_button.setAccessibleName(accessible_name)

    def show_step_confirmation(self, message: str) -> None:
        self._awaiting_step_confirmation = True
        self._set_composer_drop_hover(False)
        self._step_confirmation_label.setText(message)
        self._step_confirmation_bar.show()
        self._sync_composer_controls_enabled()

    def clear_step_confirmation(self) -> None:
        self._awaiting_step_confirmation = False
        self._step_confirmation_label.clear()
        self._step_confirmation_bar.hide()
        self._sync_composer_controls_enabled()

    # Public seams for tests and narrow consumers ------------------------------

    @property
    def editor(self) -> AutoGrowingTextEdit:
        return self._editor

    @property
    def send_button(self) -> QPushButton:
        return self._send_button

    @property
    def attach_button(self) -> QPushButton:
        return self._attach_button

    @property
    def model_picker(self) -> QComboBox:
        return self._model_picker

    @property
    def step_continue_button(self) -> QPushButton:
        return self._step_continue_button

    @property
    def step_stop_button(self) -> QPushButton:
        return self._step_stop_button

    @property
    def attached_files(self) -> list[str]:
        return self._attached_files

    @property
    def attachment_states(self) -> dict[str, ComposerAttachmentState]:
        return self._attachment_states

    @property
    def running(self) -> bool:
        return self._running

    def add_local_files(self, paths: list[str], *, notify: bool = True) -> None:
        self._add_local_files(paths, notify=notify)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self._can_accept_file_drop(event):
            event.acceptProposedAction()
            self._set_composer_drop_hover(True)
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._can_accept_file_drop(event):
            event.acceptProposedAction()
            self._set_composer_drop_hover(True)
            return
        self._set_composer_drop_hover(False)
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_composer_drop_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        self._set_composer_drop_hover(False)
        if not self._can_accept_file_drop(event):
            event.ignore()
            return
        self._add_local_files(self._local_file_paths(event))
        event.acceptProposedAction()

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self._composer_shell and event.type() == QEvent.Resize:
            self._sync_composer_drop_overlay_geometry()
        if self._is_composer_drop_target(watched):
            if event.type() in {QEvent.DragEnter, QEvent.DragMove}:
                if self._can_accept_file_drop(event):
                    event.acceptProposedAction()
                    self._set_composer_drop_hover(True)
                    return True
                self._set_composer_drop_hover(False)
                event.ignore()
                return True
            if event.type() == QEvent.Drop:
                self._set_composer_drop_hover(False)
                if self._can_accept_file_drop(event):
                    self._add_local_files(self._local_file_paths(event))
                    event.acceptProposedAction()
                    return True
                event.ignore()
                return True
            if event.type() == QEvent.DragLeave and watched is self._composer_shell:
                self._set_composer_drop_hover(False)
        return super().eventFilter(watched, event)

    def _choose_files(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            self.tr("Attach files"),
            "",
            self.tr("Data files (*.csv *.xlsx *.xls)"),
        )
        self._add_local_files(paths)

    def _configure_attach_button(self, button: QPushButton) -> None:
        button.setObjectName("attachButton")
        button.setFixedSize(34, 34)
        button.setIcon(attach_file_icon())
        button.setIconSize(QSize(16, 16))
        button.setToolTip(self.tr("Attach files"))

    def _add_local_files(self, paths: list[str], *, notify: bool = True) -> None:
        added_paths: list[str] = []
        for raw_path in paths:
            path = str(Path(raw_path).resolve())
            if Path(path).suffix.lower() not in SUPPORTED_DATASET_SUFFIXES:
                continue
            if path not in self._attached_files:
                self._attached_files.append(path)
                self._attachment_states[path] = ComposerAttachmentState(path=path)
                added_paths.append(path)
        self._refresh_attachment_chips()
        self._sync_composer_controls_enabled()
        if notify and added_paths:
            self.files_attached.emit(added_paths)

    def restore_composer(self, text: str, file_paths: list[str]) -> None:
        self._preparing_submission = False
        self._editor.setPlainText(text)
        self._attached_files.clear()
        self._attachment_states.clear()
        self._add_local_files(file_paths, notify=False)

    def set_attachment_status(
        self,
        path: str,
        status: ComposerAttachmentStatus,
        *,
        error: str | None = None,
    ) -> None:
        resolved_path = str(Path(path).resolve())
        state = self._attachment_states.get(resolved_path)
        if state is None:
            return
        state.status = status
        state.error = error
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()

    def _remove_attached_file(self, path: str, *, notify: bool = True) -> None:
        if self._running or self._preparing_submission:
            return
        resolved_path = str(Path(path).resolve())
        if resolved_path not in self._attached_files:
            return
        self._attached_files.remove(resolved_path)
        self._attachment_states.pop(resolved_path, None)
        self._refresh_attachment_chips()
        self._sync_send_button_text()
        self._sync_composer_controls_enabled()
        if notify:
            self.attachment_removed.emit(resolved_path)

    def _install_composer_drop_filters(self) -> None:
        widgets = [
            self._composer_shell,
            self._composer,
            self._attachment_bar,
            self._attach_button,
            self._editor,
            self._editor.viewport(),
            self._model_picker,
            self._send_button,
        ]
        for widget in widgets:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def _is_composer_drop_target(self, watched) -> bool:
        return isinstance(watched, QWidget) and (
            watched is self._composer_shell
            or watched is self._editor.viewport()
            or self._composer_shell.isAncestorOf(watched)
        )

    def _can_accept_file_drop(self, event) -> bool:
        if self._running or self._preparing_submission or self._awaiting_step_confirmation:
            return False
        return bool(self._local_file_paths(event))

    def _local_file_paths(self, event) -> list[str]:
        mime_data = event.mimeData()
        if mime_data is None:
            return []
        return [
            url.toLocalFile()
            for url in mime_data.urls()
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in SUPPORTED_DATASET_SUFFIXES
        ]

    def _set_composer_drop_hover(self, visible: bool) -> None:
        if visible:
            self._sync_composer_drop_overlay_geometry()
            self._composer_drop_overlay.show()
            self._composer_drop_overlay.raise_()
            return
        self._composer_drop_overlay.hide()

    def _sync_composer_drop_overlay_geometry(self) -> None:
        self._composer_drop_overlay.setGeometry(self._composer_shell.rect())

    def _handle_button_clicked(self) -> None:
        if self._running:
            self.stop_requested.emit()
            return
        if self._preparing_submission or self._awaiting_step_confirmation:
            return
        text = self._editor.toPlainText().strip()
        if self._has_unready_attachments():
            return
        files = self._ready_attachment_paths()
        if not text and not files:
            return
        self.message_submitted.emit(text, files, self.selected_fq_model_key())

    def _sync_composer_controls_enabled(self) -> None:
        can_edit = not self._running and not self._preparing_submission and not self._awaiting_step_confirmation
        self._editor.setEnabled(can_edit)
        self._attach_button.setEnabled(can_edit)
        self._send_button.setEnabled(
            not self._awaiting_step_confirmation
            and not self._has_unready_attachments()
            and (self._running or not self._preparing_submission)
        )
        self._model_picker.setEnabled(bool(self._model_options) and can_edit)
        self._step_continue_button.setEnabled(self._awaiting_step_confirmation)
        self._step_stop_button.setEnabled(self._awaiting_step_confirmation)

    def _refresh_attachment_chips(self) -> None:
        while self._attachment_layout.count() > 1:
            item = self._attachment_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._attachment_bar.setVisible(bool(self._attached_files))
        for path in self._attached_files:
            state = self._attachment_states.get(path) or ComposerAttachmentState(
                path=path,
                status=ComposerAttachmentStatus.READY,
            )
            chip = AttachmentChip(state, self)
            chip.set_removal_enabled(not self._running and not self._preparing_submission)
            chip.remove_requested.connect(self._remove_attached_file)
            self._attachment_layout.insertWidget(self._attachment_layout.count() - 1, chip)

    def _has_unready_attachments(self) -> bool:
        return any(
            state.status is not ComposerAttachmentStatus.READY
            for state in self._attachment_states.values()
        )

    def _has_pending_attachments(self) -> bool:
        return any(
            state.status is ComposerAttachmentStatus.PENDING
            for state in self._attachment_states.values()
        )

    def _ready_attachment_paths(self) -> list[str]:
        ready_paths: list[str] = []
        for path in self._attached_files:
            state = self._attachment_states.get(path)
            if state is not None and state.status is ComposerAttachmentStatus.READY:
                ready_paths.append(path)
        return ready_paths


__all__ = ["ChatComposer"]
