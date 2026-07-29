"""Header contribution for the removable AMD guided setup surface.

The Windows product exposes one Private SSH Radeon workflow.  A single Install
action validates and enrolls the target, then starts deployment; there is no
separate target editor or Save action and no coupling to the ML Worker surface.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from .amd_deployment_tasks import (
    AmdDeploymentTaskRunner,
    AmdGuidedDeploymentError,
    AmdGuidedInputField,
    AmdGuidedOperation,
    AmdGuidedPrivateInstallation,
    AmdGuidedRetirementInstallation,
    AmdGuidedTaskResult,
    AmdPrivateSshInstallCommand,
)

if TYPE_CHECKING:
    from ..services.amd.composition import AmdComposition


class AmdGuidedSetupContribution:
    """Attach the AMD setup action through the main-window contribution seam."""

    def __init__(self, composition: AmdComposition) -> None:
        self._composition = composition

    def attach(
        self,
        window: QWidget,
        header_layout: QHBoxLayout,
    ) -> _AmdGuidedSetupHandle:
        return _AmdGuidedSetupHandle(window, header_layout, self._composition)


class _AmdGuidedSetupHandle(QObject):
    """Own the optional header action and quiesce its dialog on app shutdown."""

    def __init__(
        self,
        window: QWidget,
        header_layout: QHBoxLayout,
        composition: AmdComposition,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._composition = composition
        self._shutdown = False
        self._dialog: AmdGuidedSetupDialog | None = None
        self._button = QPushButton(parent=window)
        self._button.setObjectName("amdSetupButton")
        self._button.clicked.connect(self._open_dialog)
        header_layout.addWidget(self._button)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._button.setText(self.tr("AMD setup"))
        self._button.setToolTip(self.tr("Set up the fixed Radeon profile"))
        if self._dialog is not None and isValid(self._dialog):
            self._dialog.retranslate_ui()

    def shutdown(self) -> None:
        """Close the visible dialog and suppress late worker completion delivery."""

        if self._shutdown:
            return
        self._shutdown = True
        self._button.setEnabled(False)
        self._button.hide()
        if self._dialog is not None and isValid(self._dialog):
            self._dialog.shutdown()
            self._dialog.close()
            self._dialog.deleteLater()
        self._dialog = None
        self._button.deleteLater()

    def _open_dialog(self) -> None:
        if self._shutdown:
            return
        if self._dialog is None or not isValid(self._dialog):
            self._dialog = AmdGuidedSetupDialog(self._composition, parent=self._window)
        else:
            self._dialog.refresh_inventory()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()


class AmdGuidedSetupDialog(QDialog):
    """Collect and observe one explicit Private SSH Radeon command."""

    def __init__(self, composition: AmdComposition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("amdGuidedSetupDialog")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setModal(True)
        self._shutdown = False
        self._operation_active = False
        self._active_operation_superseded = False
        self._retirement_request_active = False
        self._retirement_requested = False
        self._retirement_only = composition.retirement_only
        self._security_enrolled = False
        self._pending_installation_id = _new_installation_id()
        self._pending_target_id = _new_target_id()
        self._session_installation_id: str | None = None
        self._condition: str | None = None
        self._phase: str | None = None
        self._error_code: str | None = None
        self._invalid_field: AmdGuidedInputField | None = None
        self._inventory_entries: list[
            tuple[
                AmdGuidedPrivateInstallation | AmdGuidedRetirementInstallation,
                AmdGuidedTaskResult,
            ]
        ] = []
        self._inventory_display_numbers: dict[str, int] = {}
        self._task_runner = AmdDeploymentTaskRunner(composition, parent=self)
        self._task_runner.finished.connect(self._finish_operation)
        self._task_runner.retirement_finished.connect(self._finish_retirement_request)

        self._intro_label = QLabel(parent=self)
        self._intro_label.setObjectName("amdSetupIntroduction")
        self._intro_label.setWordWrap(True)
        self._managed_installation_label = QLabel(parent=self)
        self._managed_installation_combo = QComboBox(parent=self)
        self._managed_installation_combo.setObjectName(
            "amdManagedInstallationCombo"
        )
        self._private_heading = QLabel(parent=self)
        self._private_heading.setObjectName("amdPrivateSshHeading")
        self._host_label = QLabel(parent=self)
        self._host_input = QLineEdit(parent=self)
        self._host_input.setObjectName("amdSshHostInput")
        self._user_label = QLabel(parent=self)
        self._user_input = QLineEdit(parent=self)
        self._user_input.setObjectName("amdSshUserInput")
        self._port_label = QLabel(parent=self)
        self._port_input = QSpinBox(parent=self)
        self._port_input.setObjectName("amdSshPortInput")
        self._port_input.setRange(1, 65_535)
        self._port_input.setValue(22)
        self._identity_file_label = QLabel(parent=self)
        self._identity_file_input = QLineEdit(parent=self)
        self._identity_file_input.setObjectName("amdSshIdentityInput")
        self._identity_file_browse_button = QPushButton(parent=self)
        self._identity_file_browse_button.setObjectName("amdSshIdentityBrowseButton")
        self._pinned_host_key_label = QLabel(parent=self)
        self._pinned_host_key_input = QLineEdit(parent=self)
        self._pinned_host_key_input.setObjectName("amdSshHostKeyInput")
        self._host_key_help = QLabel(parent=self)
        self._host_key_help.setObjectName("amdSshHostKeyHelp")
        self._host_key_help.setWordWrap(True)

        self._retirement_installation_id_label = QLabel(parent=self)
        self._retirement_installation_id_input = QLineEdit(parent=self)
        self._retirement_installation_id_input.setObjectName(
            "amdRetirementInstallationIdInput"
        )

        self._condition_label = QLabel(parent=self)
        self._condition_value = QLabel(parent=self)
        self._condition_value.setObjectName("amdConditionValue")
        self._phase_label = QLabel(parent=self)
        self._phase_value = QLabel(parent=self)
        self._phase_value.setObjectName("amdPhaseValue")
        self._support_code_label = QLabel(parent=self)
        self._support_code_value = QLabel(parent=self)
        self._support_code_value.setObjectName("amdSupportCodeValue")
        self._details_label = QLabel(parent=self)
        self._details_value = QLabel(parent=self)
        self._details_value.setObjectName("amdDetailsValue")
        self._details_value.setWordWrap(True)
        self._details_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._install_button = QPushButton(parent=self)
        self._install_button.setObjectName("amdInstallButton")
        self._repair_button = QPushButton(parent=self)
        self._repair_button.setObjectName("amdRepairButton")
        self._remove_button = QPushButton(parent=self)
        self._remove_button.setObjectName("amdRemoveButton")
        self._close_button = QPushButton(parent=self)
        self._close_button.setObjectName("amdCloseButton")

        self._build_ui()
        self._wire_events()
        self._restore_existing_installation()
        self.retranslate_ui()
        self._sync_controls()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("AMD Radeon setup"))
        if self._retirement_only:
            self._intro_label.setText(
                self.tr(
                    "This build only removes an existing managed AMD installation. "
                    "Xenix discovers its durable installation identity automatically."
                )
            )
        else:
            self._intro_label.setText(
                self.tr(
                    "Install saves this Private SSH target and starts the fixed "
                    "LLM, Embedding, and OCR deployment in one step. "
                    "No separate Save action is required."
                )
            )
        self._private_heading.setText(self.tr("Private SSH Radeon"))
        self._managed_installation_label.setText(self.tr("Managed installation"))
        self._render_inventory_labels()
        self._host_label.setText(self.tr("Host"))
        self._user_label.setText(self.tr("SSH user"))
        self._port_label.setText(self.tr("SSH port"))
        self._identity_file_label.setText(self.tr("Identity file"))
        self._identity_file_browse_button.setText(self.tr("Browse…"))
        self._pinned_host_key_label.setText(self.tr("Verified server host key"))
        self._pinned_host_key_input.setPlaceholderText(
            self.tr("ssh-ed25519 AAAA… or [host]:port ssh-ed25519 AAAA…")
        )
        self._host_key_help.setText(
            self.tr(
                "Paste one verified OpenSSH server host public key. "
                "Do not paste a fingerprint, private key, or login public key."
            )
        )
        self._retirement_installation_id_label.setText(self.tr("Installation ID"))
        self._condition_label.setText(self.tr("Condition"))
        self._phase_label.setText(self.tr("Phase"))
        self._support_code_label.setText(self.tr("Support code"))
        self._details_label.setText(self.tr("Details"))
        self._install_button.setText(
            self.tr("Continue setup")
            if (
                self._session_installation_id is not None
                and not self._security_enrolled
            )
            else self.tr("Install")
        )
        self._repair_button.setText(self.tr("Repair"))
        self._remove_button.setText(
            self.tr("Retry removal") if self._retirement_requested else self.tr("Remove")
        )
        self._close_button.setText(self.tr("Close"))
        self._render_status()

    def shutdown(self) -> None:
        """Prevent a late daemon-thread result from mutating this dialog."""

        if self._shutdown:
            return
        self._shutdown = True
        self._task_runner.shutdown()
        try:
            self._task_runner.finished.disconnect(self._finish_operation)
        except (RuntimeError, TypeError):
            pass
        try:
            self._task_runner.retirement_finished.disconnect(
                self._finish_retirement_request
            )
        except (RuntimeError, TypeError):
            pass
        self._operation_active = False
        self._active_operation_superseded = False
        self._retirement_request_active = False
        self._sync_controls()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Do not hide an operation whose completion still belongs to this UI."""

        if (
            not self._shutdown
            and (self._operation_active or self._retirement_request_active)
        ):
            event.ignore()
            return
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self.resize(680, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self._intro_label)
        inventory_form = QFormLayout()
        inventory_form.setSpacing(8)
        inventory_form.addRow(
            self._managed_installation_label,
            self._managed_installation_combo,
        )
        layout.addLayout(inventory_form)
        layout.addWidget(self._private_heading)

        private_form = QFormLayout()
        private_form.setSpacing(8)
        private_form.addRow(self._host_label, self._host_input)
        private_form.addRow(self._user_label, self._user_input)
        private_form.addRow(self._port_label, self._port_input)

        identity_row = QWidget(parent=self)
        identity_layout = QHBoxLayout(identity_row)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(8)
        identity_layout.addWidget(self._identity_file_input, 1)
        identity_layout.addWidget(self._identity_file_browse_button)
        private_form.addRow(self._identity_file_label, identity_row)
        private_form.addRow(self._pinned_host_key_label, self._pinned_host_key_input)
        layout.addLayout(private_form)
        layout.addWidget(self._host_key_help)

        retirement_form = QFormLayout()
        retirement_form.setSpacing(8)
        retirement_form.addRow(
            self._retirement_installation_id_label,
            self._retirement_installation_id_input,
        )
        layout.addLayout(retirement_form)

        status_form = QFormLayout()
        status_form.setSpacing(6)
        status_form.addRow(self._condition_label, self._condition_value)
        status_form.addRow(self._phase_label, self._phase_value)
        status_form.addRow(self._support_code_label, self._support_code_value)
        status_form.addRow(self._details_label, self._details_value)
        layout.addLayout(status_form)
        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addWidget(self._install_button)
        actions.addWidget(self._repair_button)
        actions.addWidget(self._remove_button)
        actions.addStretch(1)
        actions.addWidget(self._close_button)
        layout.addLayout(actions)

        private_widgets = (
            self._private_heading,
            self._host_label,
            self._host_input,
            self._user_label,
            self._user_input,
            self._port_label,
            self._port_input,
            self._identity_file_label,
            identity_row,
            self._pinned_host_key_label,
            self._pinned_host_key_input,
            self._host_key_help,
        )
        for widget in private_widgets:
            widget.setVisible(not self._retirement_only)
        self._retirement_installation_id_label.setVisible(self._retirement_only)
        self._retirement_installation_id_input.setVisible(self._retirement_only)
        self._retirement_installation_id_input.setReadOnly(True)

    def _wire_events(self) -> None:
        self._managed_installation_combo.currentIndexChanged.connect(
            self._select_inventory_item
        )
        self._identity_file_browse_button.clicked.connect(self._choose_identity_file)
        self._install_button.clicked.connect(self._start_install)
        self._repair_button.clicked.connect(self._start_repair)
        self._remove_button.clicked.connect(self._start_remove)
        self._close_button.clicked.connect(self.close)
        for input_widget in (
            self._host_input,
            self._user_input,
            self._identity_file_input,
            self._pinned_host_key_input,
            self._retirement_installation_id_input,
        ):
            input_widget.textChanged.connect(self._input_changed)
        self._port_input.valueChanged.connect(self._input_changed)

    def _input_changed(self, *_args: object) -> None:
        if self._phase == "validation":
            self._clear_invalid_field()
            self._condition = None
            self._phase = None
            self._error_code = None
            self._render_status()
        self._sync_controls()

    def refresh_inventory(self) -> None:
        """Refresh durable identities when the persistent dialog is reopened."""

        if (
            self._shutdown
            or self._operation_active
            or self._retirement_request_active
        ):
            return
        self._restore_existing_installation()
        self.retranslate_ui()
        self._sync_controls()

    def _restore_existing_installation(self) -> None:
        selected_installation_id = self._session_installation_id
        had_managed_selection = any(
            installation.installation_id == selected_installation_id
            for installation, _result in self._inventory_entries
        )
        try:
            inventory = (
                self._task_runner.retirement_inventory()
                if self._retirement_only
                else self._task_runner.private_inventory()
            )
        except AmdGuidedDeploymentError as exc:
            self._condition = "needs_attention"
            self._phase = "inventory"
            self._error_code = exc.error_code
            return
        except Exception:
            self._condition = "failed"
            self._phase = "inventory"
            self._error_code = "amd_operation_failed"
            return
        self._inventory_entries = list(inventory)
        selected_index = next(
            (
                index
                for index, (installation, _result) in enumerate(
                    self._inventory_entries
                )
                if installation.installation_id == selected_installation_id
            ),
            0 if self._inventory_entries else -1,
        )
        self._render_inventory_labels(selected_index=selected_index)
        if selected_index < 0:
            if had_managed_selection:
                self._condition = "removed"
                self._phase = "already_removed"
                self._error_code = None
                self._retirement_requested = False
                if self._retirement_only:
                    self._session_installation_id = None
                    self._retirement_installation_id_input.clear()
                else:
                    self._reset_private_command_identity()
            return
        self._adopt_inventory_item(selected_index)

    def _select_inventory_item(self, index: int) -> None:
        if (
            self._shutdown
            or self._operation_active
            or self._retirement_request_active
            or not 0 <= index < len(self._inventory_entries)
        ):
            return
        self._adopt_inventory_item(index)
        self.retranslate_ui()
        self._sync_controls()

    def _adopt_inventory_item(self, index: int) -> None:
        installation, result = self._inventory_entries[index]
        if isinstance(installation, AmdGuidedPrivateInstallation):
            self._adopt_existing_installation(installation, result)
        elif isinstance(installation, AmdGuidedRetirementInstallation):
            self._adopt_retirement_installation(installation, result)

    def _render_inventory_labels(self, *, selected_index: int | None = None) -> None:
        if selected_index is None:
            selected_index = self._managed_installation_combo.currentIndex()
        self._managed_installation_combo.blockSignals(True)
        try:
            self._managed_installation_combo.clear()
            for installation, _result in self._inventory_entries:
                number = self._inventory_display_number(
                    installation.installation_id
                )
                if isinstance(installation, AmdGuidedPrivateInstallation):
                    label = self.tr("Private SSH installation {number}").format(
                        number=number
                    )
                elif installation.placement == "local_linux":
                    label = self.tr("Historical Local installation {number}").format(
                        number=number
                    )
                else:
                    label = self.tr(
                        "Historical Private SSH installation {number}"
                    ).format(
                        number=number
                    )
                self._managed_installation_combo.addItem(label)
            if 0 <= selected_index < len(self._inventory_entries):
                self._managed_installation_combo.setCurrentIndex(selected_index)
            else:
                self._managed_installation_combo.setCurrentIndex(-1)
        finally:
            self._managed_installation_combo.blockSignals(False)
        self._sync_inventory_visibility()

    def _inventory_display_number(self, installation_id: str) -> int:
        number = self._inventory_display_numbers.get(installation_id)
        if number is None:
            number = len(self._inventory_display_numbers) + 1
            self._inventory_display_numbers[installation_id] = number
        return number

    def _sync_inventory_visibility(self) -> None:
        has_unselected_item = (
            bool(self._inventory_entries)
            and self._managed_installation_combo.currentIndex() < 0
        )
        visible = len(self._inventory_entries) > 1 or has_unselected_item
        self._managed_installation_label.setVisible(visible)
        self._managed_installation_combo.setVisible(visible)

    def _remove_inventory_item(self, installation_id: str) -> None:
        removed_index = next(
            (
                index
                for index, (installation, _result) in enumerate(
                    self._inventory_entries
                )
                if installation.installation_id == installation_id
            ),
            None,
        )
        if removed_index is None:
            return
        self._inventory_entries.pop(removed_index)
        # Keep the terminal Remove result visible.  If another installation
        # remains, the selector asks the user to choose it explicitly.
        self._render_inventory_labels(selected_index=-1)

    def _reset_private_command_identity(self) -> None:
        """Start a fresh command after the previous durable identity disappears."""

        self._pending_installation_id = _new_installation_id()
        self._pending_target_id = _new_target_id()
        self._session_installation_id = None
        self._security_enrolled = False
        self._retirement_installation_id_input.clear()
        self._host_input.clear()
        self._user_input.clear()
        self._port_input.setValue(22)
        self._identity_file_input.clear()
        self._pinned_host_key_input.clear()

    def _adopt_existing_installation(
        self,
        installation: AmdGuidedPrivateInstallation,
        result: AmdGuidedTaskResult,
    ) -> None:
        changing_installation = (
            self._session_installation_id != installation.installation_id
        )
        self._retirement_requested = False
        self._clear_invalid_field()
        self._pending_installation_id = installation.installation_id
        self._pending_target_id = installation.target_id
        self._session_installation_id = installation.installation_id
        self._security_enrolled = installation.security_enrolled
        self._host_input.setText(installation.host)
        self._user_input.setText(installation.user)
        self._port_input.setValue(installation.port)
        if changing_installation:
            # These values are user-authored security input, not installation
            # inventory.  They must never cross from one selected identity to
            # another.
            self._identity_file_input.clear()
            self._pinned_host_key_input.clear()
        self._retirement_installation_id_input.setText(
            installation.installation_id
        )
        self._condition = result.condition
        self._phase = result.phase
        self._error_code = result.error_code
        if (
            result.operation is AmdGuidedOperation.REMOVE
            and result.condition != "removed"
        ):
            self._retirement_requested = True
        elif (
            not installation.security_enrolled
            and installation.inventory_error_code is None
        ):
            self._condition = "needs_attention"
            self._phase = "enrollment"
            self._error_code = "amd_ssh_enrollment_incomplete"

    def _adopt_retirement_installation(
        self,
        installation: AmdGuidedRetirementInstallation,
        result: AmdGuidedTaskResult,
    ) -> None:
        changing_installation = (
            self._session_installation_id != installation.installation_id
        )
        self._retirement_requested = False
        self._clear_invalid_field()
        self._session_installation_id = installation.installation_id
        if changing_installation:
            self._identity_file_input.clear()
            self._pinned_host_key_input.clear()
        self._retirement_installation_id_input.setText(
            installation.installation_id
        )
        self._condition = result.condition
        self._phase = result.phase
        self._error_code = result.error_code
        if (
            result.operation is AmdGuidedOperation.REMOVE
            and result.condition != "removed"
        ):
            self._retirement_requested = True

    def _choose_identity_file(self) -> None:
        if (
            self._shutdown
            or self._operation_active
            or self._retirement_request_active
            or self._retirement_requested
        ):
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose an identity file"),
            self._identity_file_input.text().strip(),
            self.tr("All files (*)"),
        )
        if path:
            self._identity_file_input.setText(path)

    def _start_install(self) -> None:
        if (
            self._shutdown
            or self._operation_active
            or self._retirement_request_active
            or self._retirement_requested
            or self._retirement_only
            or (
                self._session_installation_id is not None
                and self._security_enrolled
            )
        ):
            return
        command = self._install_command()
        try:
            self._task_runner.validate_install(command)
        except AmdGuidedDeploymentError as exc:
            self._show_validation_error(exc)
            return
        except Exception:
            self._show_operation_error("amd_operation_failed")
            return
        if self._task_runner.start_install(command):
            # This volatile pending ID permits an immediate explicit Remove to
            # wait for the tiny enrollment/SQLite race.  The result later tells
            # us truthfully whether a durable installation ever existed.
            self._session_installation_id = command.installation_id
            self._begin_operation(AmdGuidedOperation.INSTALL)
            return
        self._show_operation_error("amd_worker_unavailable")

    def _start_repair(self) -> None:
        if (
            self._shutdown
            or self._operation_active
            or self._retirement_request_active
            or self._retirement_requested
            or self._retirement_only
            or self._session_installation_id is None
        ):
            return
        if self._task_runner.start_repair(self._session_installation_id):
            self._begin_operation(AmdGuidedOperation.REPAIR)
            return
        self._show_operation_error("amd_worker_unavailable")

    def _start_remove(self) -> None:
        if self._shutdown or self._retirement_request_active:
            return
        installation_id = (
            self._retirement_installation_id_input.text().strip()
            if self._retirement_only
            else self._session_installation_id
        )
        if not installation_id:
            self._show_operation_error("amd_installation_id_required")
            if self._retirement_only:
                self._retirement_installation_id_input.setFocus(Qt.OtherFocusReason)
            return
        if self._task_runner.start_remove(installation_id):
            self._session_installation_id = installation_id
            self._retirement_request_active = True
            if self._operation_active:
                self._active_operation_superseded = True
            # This is the latest user intent immediately, not only after a
            # successful acknowledgement.  Late Install/Repair results may
            # never overwrite the Remove outcome or its support code.
            self._retirement_requested = True
            self._condition = "working"
            self._phase = "retirement_requesting"
            self._error_code = None
            self._clear_invalid_field()
            self._render_status()
            self._sync_controls()
            return
        self._show_operation_error("amd_worker_unavailable")

    def _install_command(self) -> AmdPrivateSshInstallCommand:
        identity_value = self._identity_file_input.text().strip()
        return AmdPrivateSshInstallCommand(
            installation_id=self._pending_installation_id,
            target_id=self._pending_target_id,
            host=self._host_input.text().strip(),
            user=self._user_input.text().strip(),
            port=self._port_input.value(),
            identity_file=Path(identity_value) if identity_value else None,
            pinned_host_key=self._pinned_host_key_input.text().strip(),
        )

    def _begin_operation(self, operation: AmdGuidedOperation) -> None:
        self._operation_active = True
        self._active_operation_superseded = False
        self._condition = "working"
        self._phase = operation.value
        self._error_code = None
        self._clear_invalid_field()
        self.retranslate_ui()
        self._sync_controls()

    def _finish_operation(self, result: object) -> None:
        if self._shutdown:
            return
        self._operation_active = False
        invalid_field: AmdGuidedInputField | None = None
        if self._active_operation_superseded:
            self._active_operation_superseded = False
            self._sync_controls()
            return
        if self._retirement_request_active or self._retirement_requested:
            self._sync_controls()
            return
        if not isinstance(result, AmdGuidedTaskResult):
            self._condition = "failed"
            self._phase = "failed"
            self._error_code = "amd_operation_failed"
        else:
            self._condition = (
                "needs_attention" if result.input_field is not None else result.condition
            )
            self._phase = (
                "validation" if result.input_field is not None else result.phase
            )
            self._error_code = result.error_code
            self._security_enrolled = result.security_enrolled
            self._session_installation_id = (
                result.installation_id
                if result.installation_available is not False
                else None
            )
            invalid_field = result.input_field
            self._record_operation_result(result)
        self.retranslate_ui()
        self._sync_controls()
        if invalid_field is not None:
            self._set_invalid_field(invalid_field)

    def _record_operation_result(self, result: AmdGuidedTaskResult) -> None:
        """Keep the dialog's inventory projection coherent until the next refresh."""

        if self._retirement_only:
            return
        if result.installation_available is False:
            if result.operation is AmdGuidedOperation.REPAIR:
                self._remove_inventory_item(result.installation_id)
                self._reset_private_command_identity()
            return

        inventory_error_code = (
            result.error_code
            if result.error_code == "amd_ssh_security_unavailable"
            else None
        )
        existing_index = next(
            (
                index
                for index, (installation, _cached_result) in enumerate(
                    self._inventory_entries
                )
                if installation.installation_id == result.installation_id
            ),
            None,
        )
        if (
            existing_index is None
            and result.installation_available is None
        ):
            return
        if existing_index is None:
            installation = AmdGuidedPrivateInstallation(
                installation_id=result.installation_id,
                target_id=self._pending_target_id,
                host=self._host_input.text().strip(),
                user=self._user_input.text().strip(),
                port=self._port_input.value(),
                security_enrolled=result.security_enrolled,
                desired_presence=True,
                lifecycle_state="active",
                status=None,
                inventory_error_code=inventory_error_code,
            )
            self._inventory_entries.append((installation, result))
            existing_index = len(self._inventory_entries) - 1
        else:
            installation, _cached_result = self._inventory_entries[existing_index]
            if not isinstance(installation, AmdGuidedPrivateInstallation):
                return
            self._inventory_entries[existing_index] = (
                replace(
                    installation,
                    security_enrolled=result.security_enrolled,
                    desired_presence=True,
                    lifecycle_state="active",
                    inventory_error_code=inventory_error_code,
                ),
                result,
            )
        self._render_inventory_labels(selected_index=existing_index)

    def _finish_retirement_request(self, result: object) -> None:
        if self._shutdown:
            return
        self._retirement_request_active = False
        if not isinstance(result, AmdGuidedTaskResult):
            self._condition = "failed"
            self._phase = "failed"
            self._error_code = "amd_operation_failed"
        else:
            self._condition = result.condition
            self._phase = result.phase
            self._error_code = result.error_code
            self._security_enrolled = result.security_enrolled
            self._record_retirement_result(result)
            if (
                result.condition == "removed"
                or result.installation_available is False
            ):
                self._retirement_requested = False
                self._remove_inventory_item(result.installation_id)
                if self._retirement_only:
                    self._session_installation_id = None
                    self._retirement_installation_id_input.clear()
                else:
                    self._reset_private_command_identity()
        self.retranslate_ui()
        self._sync_controls()

    def _record_retirement_result(self, result: AmdGuidedTaskResult) -> None:
        """Cache the latest Remove authority so selection cannot revive stale UI."""

        if result.installation_available is False:
            return
        existing_index = next(
            (
                index
                for index, (installation, _cached_result) in enumerate(
                    self._inventory_entries
                )
                if installation.installation_id == result.installation_id
            ),
            None,
        )
        if (
            existing_index is None
            and result.installation_available is None
        ):
            return
        if existing_index is None:
            if self._retirement_only:
                return
            installation: (
                AmdGuidedPrivateInstallation | AmdGuidedRetirementInstallation
            ) = AmdGuidedPrivateInstallation(
                installation_id=result.installation_id,
                target_id=self._pending_target_id,
                host=self._host_input.text().strip(),
                user=self._user_input.text().strip(),
                port=self._port_input.value(),
                security_enrolled=result.security_enrolled,
                desired_presence=False,
                lifecycle_state="retiring",
                status=None,
            )
            self._inventory_entries.append((installation, result))
            existing_index = len(self._inventory_entries) - 1
        else:
            installation, _cached_result = self._inventory_entries[existing_index]
            if isinstance(installation, AmdGuidedPrivateInstallation):
                installation = replace(
                    installation,
                    security_enrolled=result.security_enrolled,
                    desired_presence=False,
                    lifecycle_state="retiring",
                )
            elif isinstance(installation, AmdGuidedRetirementInstallation):
                installation = replace(
                    installation,
                    desired_presence=False,
                    lifecycle_state="retiring",
                )
            self._inventory_entries[existing_index] = (installation, result)
        self._render_inventory_labels(selected_index=existing_index)

    def _show_validation_error(self, error: AmdGuidedDeploymentError) -> None:
        self._condition = "needs_attention"
        self._phase = "validation"
        self._error_code = error.error_code
        self._set_invalid_field(error.field)
        self._render_status()
        self._sync_controls()

    def _show_operation_error(self, error_code: str) -> None:
        self._condition = "failed"
        self._phase = "failed"
        self._error_code = error_code
        self._render_status()
        self._sync_controls()

    def _set_invalid_field(self, field: AmdGuidedInputField | None) -> None:
        self._clear_invalid_field()
        self._invalid_field = field
        widget = self._widget_for_field(field)
        if widget is None:
            return
        widget.setStyleSheet("border: 1px solid #d92d20;")
        widget.setFocus(Qt.OtherFocusReason)
        if isinstance(widget, QLineEdit):
            widget.selectAll()
        elif isinstance(widget, QSpinBox):
            widget.lineEdit().selectAll()

    def _clear_invalid_field(self) -> None:
        widget = self._widget_for_field(self._invalid_field)
        if widget is not None:
            widget.setStyleSheet("")
        self._invalid_field = None

    def _widget_for_field(
        self,
        field: AmdGuidedInputField | None,
    ) -> QLineEdit | QSpinBox | None:
        return {
            AmdGuidedInputField.HOST: self._host_input,
            AmdGuidedInputField.USER: self._user_input,
            AmdGuidedInputField.PORT: self._port_input,
            AmdGuidedInputField.IDENTITY_FILE: self._identity_file_input,
            AmdGuidedInputField.PINNED_HOST_KEY: self._pinned_host_key_input,
        }.get(field)

    def _sync_controls(self) -> None:
        self._managed_installation_combo.setEnabled(
            not self._shutdown
            and not self._operation_active
            and not self._retirement_request_active
        )
        self._sync_inventory_visibility()
        editable = (
            not self._shutdown
            and not self._operation_active
            and not self._retirement_request_active
            and not self._retirement_requested
        )
        private_continue_available = (
            editable
            and not self._retirement_only
            and (
                self._session_installation_id is not None
                or not self._inventory_entries
            )
            and (
                self._session_installation_id is None
                or not self._security_enrolled
            )
        )
        endpoint_editable = (
            private_continue_available
            and self._session_installation_id is None
        )
        for widget in (
            self._host_input,
            self._user_input,
            self._port_input,
        ):
            widget.setEnabled(endpoint_editable)
        for widget in (
            self._identity_file_input,
            self._identity_file_browse_button,
            self._pinned_host_key_input,
        ):
            widget.setEnabled(private_continue_available)
        self._retirement_installation_id_input.setEnabled(False)
        self._install_button.setVisible(not self._retirement_only)
        self._repair_button.setVisible(not self._retirement_only)
        self._install_button.setEnabled(private_continue_available)
        self._repair_button.setEnabled(
            editable
            and not self._retirement_only
            and self._session_installation_id is not None
            and self._security_enrolled
            and self._condition != "removed"
        )
        has_removal_target = (
            bool(self._retirement_installation_id_input.text().strip())
            if self._retirement_only
            else self._session_installation_id is not None
        )
        self._remove_button.setEnabled(
            not self._shutdown
            and not self._retirement_request_active
            and has_removal_target
            and self._condition != "removed"
        )
        self._close_button.setEnabled(
            not self._shutdown
            and not self._operation_active
            and not self._retirement_request_active
        )

    def _render_status(self) -> None:
        self._condition_value.setText(self._status_value(self._condition))
        self._phase_value.setText(self._status_value(self._phase))
        self._support_code_value.setText(
            self._error_code if self._error_code is not None else self.tr("None")
        )
        self._details_value.setText(self._details_message())
        has_error = self._error_code is not None
        self._details_value.setStyleSheet(
            "color: #d92d20;" if has_error else ""
        )

    def _status_value(self, value: str | None) -> str:
        labels = {
            "needs_attention": self.tr("Needs attention"),
            "working": self.tr("Working"),
            "failed": self.tr("Failed"),
            "not_materialized": self.tr("Not installed"),
            "installing": self.tr("Installing"),
            "degraded": self.tr("Degraded"),
            "operational": self.tr("Operational"),
            "incompatible": self.tr("Incompatible"),
            "retiring": self.tr("Retiring"),
            "removal_blocked": self.tr("Removal blocked"),
            "removed": self.tr("Removed"),
            "validation": self.tr("Validating input"),
            "inventory": self.tr("Loading managed installation"),
            "enrollment": self.tr("Saving target security"),
            "install": self.tr("Installing"),
            "repair": self.tr("Repairing"),
            "planned": self.tr("Planned"),
            "reconciling": self.tr("Reconciling"),
            "verified": self.tr("Verified"),
            "registered": self.tr("Registered"),
            "materialization_failed": self.tr("Deployment failed"),
            "projection_blocked": self.tr("Provider registration blocked"),
            "retirement_requesting": self.tr("Requesting safe retirement"),
            "retirement_requested": self.tr("Removal requested"),
            "retirement_already_requested": self.tr("Removal already requested"),
            "already_removed": self.tr("Already removed"),
        }
        return labels.get(value, value if value is not None else self.tr("Not available"))

    def _details_message(self) -> str:
        code = self._error_code
        if code is not None:
            return self._error_message(code)
        if self._condition == "working":
            if self._phase == "retirement_requesting":
                return self.tr("Recording the removal request safely.")
            return self.tr(
                "Checking the target and advancing the managed deployment. "
                "This may take several minutes."
            )
        if self._condition == "operational":
            return self.tr(
                "LLM, Embedding, and OCR are operational through the managed Radeon target."
            )
        if self._condition == "retiring":
            return self.tr(
                "Removal is durably requested and physical cleanup continues safely."
            )
        if self._condition == "removed":
            return self.tr("The managed AMD installation has been removed.")
        if self._retirement_only:
            return self.tr(
                "Xenix will use the durable managed installation identity shown above."
            )
        return self.tr(
            "Complete the SSH fields and choose Install. "
            "Install also saves the target; there is no separate Save action."
        )

    def _error_message(self, code: str) -> str:
        messages = {
            "amd_ssh_host_required": self.tr("Enter the SSH host."),
            "amd_ssh_host_invalid": self.tr(
                "Enter a valid IP address or DNS host name without spaces."
            ),
            "amd_ssh_user_required": self.tr("Enter the SSH user."),
            "amd_ssh_user_invalid": self.tr(
                "Enter a valid OpenSSH user name."
            ),
            "amd_ssh_port_invalid": self.tr(
                "Enter an SSH port between 1 and 65535."
            ),
            "amd_ssh_identity_required": self.tr(
                "Choose the private identity file used for SSH authentication."
            ),
            "amd_ssh_identity_invalid": self.tr(
                "Choose an identity file by its absolute local path."
            ),
            "amd_ssh_identity_unavailable": self.tr(
                "The selected identity file is not available. Choose an existing file."
            ),
            "amd_ssh_host_key_required": self.tr(
                "Paste the verified server host public key."
            ),
            "amd_ssh_host_key_invalid": self.tr(
                "Paste one complete OpenSSH server host public key, not a fingerprint, "
                "private key, or login public key."
            ),
            "amd_ssh_security_conflict": self.tr(
                "These security details conflict with an existing enrollment. "
                "Verify the identity file and server host key."
            ),
            "amd_ssh_security_capacity_reached": self.tr(
                "The local AMD target enrollment limit has been reached."
            ),
            "amd_ssh_security_unavailable": self.tr(
                "Xenix could not save or read the local SSH security record."
            ),
            "amd_ssh_enrollment_incomplete": self.tr(
                "The installation identity was saved safely, but SSH security setup "
                "did not finish. Re-enter the identity file and verified host key, "
                "then choose Continue setup."
            ),
            "amd_target_conflict": self.tr(
                "This target identity conflicts with an existing immutable enrollment."
            ),
            "amd_installation_conflict": self.tr(
                "This installation identity conflicts with an existing deployment."
            ),
            "amd_installation_already_exists": self.tr(
                "Another managed Private SSH installation already exists. "
                "Repair or remove it before creating a new one."
            ),
            "amd_installation_inventory_conflict": self.tr(
                "More than one active managed Private SSH installation exists. "
                "Use the diagnostic bundle to resolve the conflicting inventory safely."
            ),
            "amd_installation_inventory_invalid": self.tr(
                "The managed AMD installation inventory is incomplete or damaged."
            ),
            "amd_ssh_client_unavailable": self.tr(
                "Windows OpenSSH is unavailable. Install or enable the OpenSSH client."
            ),
            "amd_ssh_host_trust_failed": self.tr(
                "The server host key did not match. Stop and verify the key with the target owner."
            ),
            "amd_ssh_authentication_failed": self.tr(
                "SSH authentication failed. Verify the SSH user and identity file."
            ),
            "amd_ssh_connection_timeout": self.tr(
                "The SSH connection timed out. Verify the host, port, and target availability."
            ),
            "amd_ssh_connection_failed": self.tr(
                "The SSH target reset or rejected the connection. "
                "Verify the host, port, and cloud instance state."
            ),
            "amd_ssh_forward_failed": self.tr(
                "Xenix could not establish the private loopback connection to the managed services."
            ),
            "amd_ssh_target_unavailable": self.tr(
                "The enrolled SSH target or its local security material is unavailable."
            ),
            "amd_target_observation_failed": self.tr(
                "Xenix could not inspect the Radeon target safely."
            ),
            "amd_private_recipe_failed": self.tr(
                "The managed Radeon services could not be deployed or verified."
            ),
            "materialization_failed": self.tr(
                "The managed Radeon services did not finish deployment."
            ),
            "provider_projection_blocked": self.tr(
                "Deployment completed, but one or more provider registrations were blocked."
            ),
            "amd_deployment_degraded": self.tr(
                "The installation exists, but one or more LLM, Embedding, or OCR components failed."
            ),
            "amd_deployment_incomplete": self.tr(
                "The installation has not reached operational state. Choose Repair to continue forward."
            ),
            "amd_not_materialized": self.tr(
                "The target was enrolled, but the managed services were not installed."
            ),
            "amd_installation_retiring": self.tr(
                "This installation is being removed and cannot be reactivated."
            ),
            "amd_removal_blocked": self.tr(
                "Safe physical cleanup is blocked. Retry removal after restoring target access."
            ),
            "physical_cleanup_blocked": self.tr(
                "Xenix could not establish the trusted control session needed for "
                "physical cleanup. Restore target access, then retry removal."
            ),
            "provider_removal_blocked": self.tr(
                "Provider settings could not be removed safely. Retry removal or "
                "use the diagnostic bundle."
            ),
            "amd_installation_not_found": self.tr(
                "No managed AMD installation exists with that installation ID."
            ),
            "amd_installation_id_required": self.tr(
                "Enter the installation ID to remove."
            ),
            "amd_profile_catalog_invalid": self.tr(
                "The bundled Radeon deployment profile is unavailable."
            ),
            "amd_profile_unavailable": self.tr(
                "The bundled Radeon deployment profile is unavailable."
            ),
            "amd_placement_unavailable": self.tr(
                "Private SSH Radeon deployment is unavailable in this build."
            ),
            "amd_retirement_only": self.tr(
                "This build permits removal only; new AMD installations are disabled."
            ),
            "amd_deployment_closed": self.tr(
                "AMD deployment is shutting down. Reopen Xenix and try again."
            ),
            "amd_worker_unavailable": self.tr(
                "Xenix could not start the deployment worker. Try again."
            ),
            "amd_request_invalid": self.tr(
                "The guided deployment request is invalid. Review the form and try again."
            ),
            "amd_status_invalid": self.tr(
                "Xenix received an invalid deployment status."
            ),
            "amd_operation_failed": self.tr(
                "The AMD operation failed unexpectedly. Use the support code with the diagnostic bundle."
            ),
        }
        message = messages.get(code)
        if message is not None:
            return message
        if code.startswith("amd_compatibility_"):
            return self._compatibility_message(code)
        return self.tr(
            "The AMD operation could not complete. Use the support code with the diagnostic bundle."
        )

    def _compatibility_message(self, code: str) -> str:
        messages = {
            "amd_compatibility_profile_not_admitted": self.tr(
                "The bundled Radeon profile is not admitted for product deployment."
            ),
            "amd_compatibility_component_not_admitted": self.tr(
                "At least one bundled LLM, Embedding, or OCR component is not admitted."
            ),
            "amd_compatibility_cell_not_admitted": self.tr(
                "This Radeon software and hardware cell is not admitted."
            ),
            "amd_compatibility_target_fact_missing": self.tr(
                "The target did not provide all required compatibility facts."
            ),
            "amd_compatibility_os_name_mismatch": self.tr(
                "The target operating system is unsupported."
            ),
            "amd_compatibility_os_version_mismatch": self.tr(
                "The target operating-system version is unsupported."
            ),
            "amd_compatibility_kernel_version_mismatch": self.tr(
                "The target Linux kernel version is unsupported."
            ),
            "amd_compatibility_architecture_mismatch": self.tr(
                "The target CPU architecture is unsupported."
            ),
            "amd_compatibility_gpu_architecture_mismatch": self.tr(
                "The Radeon GPU architecture is unsupported."
            ),
            "amd_compatibility_driver_version_mismatch": self.tr(
                "The AMD GPU driver version is unsupported."
            ),
            "amd_compatibility_rocm_version_mismatch": self.tr(
                "The ROCm version is unsupported."
            ),
            "amd_compatibility_hip_version_mismatch": self.tr(
                "The HIP version is unsupported."
            ),
            "amd_compatibility_python_version_mismatch": self.tr(
                "The target Python version is unsupported."
            ),
            "amd_compatibility_gpu_count_insufficient": self.tr(
                "The target does not have enough admitted Radeon GPUs."
            ),
            "amd_compatibility_vram_insufficient": self.tr(
                "The target does not have enough free GPU memory."
            ),
            "amd_compatibility_system_memory_insufficient": self.tr(
                "The target does not have enough free system memory."
            ),
            "amd_compatibility_persistent_storage_insufficient": self.tr(
                "The target does not have enough free persistent storage."
            ),
            "amd_compatibility_capacity_requirement_unmeasured": self.tr(
                "The bundled profile is missing a required capacity measurement."
            ),
            "amd_compatibility_failed": self.tr(
                "The target does not satisfy the fixed Radeon deployment profile."
            ),
        }
        return messages.get(
            code,
            self.tr("The target does not satisfy the fixed Radeon deployment profile."),
        )


def _new_installation_id() -> str:
    return f"amd-installation-{uuid4().hex}"


def _new_target_id() -> str:
    return f"amd-target-{uuid4().hex}"


__all__ = ["AmdGuidedSetupContribution", "AmdGuidedSetupDialog"]
