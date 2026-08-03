"""Header contribution for the removable AMD guided setup surface.

This module is intentionally an optional leaf: application composition imports
it only when the AMD slice is enabled, and the dialog communicates solely with
the supplied composition through explicit background commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from .amd_deployment_tasks import (
    AmdDeploymentTaskRunner,
    AmdGuidedInstallRequest,
    AmdGuidedOperation,
    AmdGuidedPlacement,
    AmdGuidedTaskResult,
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
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()


class AmdGuidedSetupDialog(QDialog):
    """Collect one explicit Local Linux or Private SSH Radeon request."""

    def __init__(self, composition: AmdComposition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setModal(True)
        self._shutdown = False
        self._operation_active = False
        self._retirement_request_active = False
        self._retirement_requested = False
        self._retirement_only = composition.retirement_only
        self._session_installation_id: str | None = None
        self._condition: str | None = None
        self._phase: str | None = None
        self._error_code: str | None = None
        self._task_runner = AmdDeploymentTaskRunner(composition, parent=self)
        self._task_runner.finished.connect(self._finish_operation)
        self._task_runner.retirement_finished.connect(self._finish_retirement_request)

        self._local_linux_radio = QRadioButton(parent=self)
        self._private_ssh_radio = QRadioButton(parent=self)
        self._placement_group = QButtonGroup(self)
        self._placement_group.addButton(self._local_linux_radio)
        self._placement_group.addButton(self._private_ssh_radio)
        self._local_linux_radio.setChecked(True)

        self._installation_id_label = QLabel(parent=self)
        self._installation_id_input = QLineEdit(_new_installation_id(), parent=self)
        self._private_fields = QWidget(parent=self)
        self._target_id_label = QLabel(parent=self._private_fields)
        self._target_id_input = QLineEdit(_new_target_id(), parent=self._private_fields)
        self._host_label = QLabel(parent=self._private_fields)
        self._host_input = QLineEdit(parent=self._private_fields)
        self._user_label = QLabel(parent=self._private_fields)
        self._user_input = QLineEdit(parent=self._private_fields)
        self._port_label = QLabel(parent=self._private_fields)
        self._port_input = QSpinBox(parent=self._private_fields)
        self._port_input.setRange(1, 65_535)
        self._port_input.setValue(22)
        self._identity_file_label = QLabel(parent=self._private_fields)
        self._identity_file_input = QLineEdit(parent=self._private_fields)
        self._identity_file_browse_button = QPushButton(parent=self._private_fields)
        self._pinned_host_key_label = QLabel(parent=self._private_fields)
        self._pinned_host_key_input = QLineEdit(parent=self._private_fields)

        self._condition_label = QLabel(parent=self)
        self._condition_value = QLabel(parent=self)
        self._phase_label = QLabel(parent=self)
        self._phase_value = QLabel(parent=self)
        self._error_code_label = QLabel(parent=self)
        self._error_code_value = QLabel(parent=self)
        self._install_button = QPushButton(parent=self)
        self._repair_button = QPushButton(parent=self)
        self._remove_button = QPushButton(parent=self)
        self._close_button = QPushButton(parent=self)

        self._build_ui()
        self._wire_events()
        self.retranslate_ui()
        self._sync_placement_fields()
        self._sync_controls()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("AMD Radeon setup"))
        self._local_linux_radio.setText(self.tr("Local Linux Radeon"))
        self._private_ssh_radio.setText(self.tr("Private SSH Radeon"))
        self._installation_id_label.setText(self.tr("Installation ID"))
        self._target_id_label.setText(self.tr("Target ID"))
        self._host_label.setText(self.tr("Host"))
        self._user_label.setText(self.tr("User"))
        self._port_label.setText(self.tr("Port"))
        self._identity_file_label.setText(self.tr("Identity file"))
        self._identity_file_browse_button.setText(self.tr("Browse…"))
        self._pinned_host_key_label.setText(self.tr("Pinned public host key"))
        self._pinned_host_key_input.setPlaceholderText(
            self.tr("OpenSSH public key")
        )
        self._condition_label.setText(self.tr("Condition"))
        self._phase_label.setText(self.tr("Phase"))
        self._error_code_label.setText(self.tr("Error code"))
        self._install_button.setText(self.tr("Install"))
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
            self._task_runner.retirement_finished.disconnect(self._finish_retirement_request)
        except (RuntimeError, TypeError):
            pass
        self._operation_active = False
        self._retirement_request_active = False
        self._sync_controls()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self.resize(620, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        placement_row = QHBoxLayout()
        placement_row.addWidget(self._local_linux_radio)
        placement_row.addWidget(self._private_ssh_radio)
        placement_row.addStretch(1)
        layout.addLayout(placement_row)

        common_form = QFormLayout()
        common_form.setSpacing(8)
        common_form.addRow(self._installation_id_label, self._installation_id_input)
        layout.addLayout(common_form)

        private_form = QFormLayout(self._private_fields)
        private_form.setSpacing(8)
        private_form.addRow(self._target_id_label, self._target_id_input)
        private_form.addRow(self._host_label, self._host_input)
        private_form.addRow(self._user_label, self._user_input)
        private_form.addRow(self._port_label, self._port_input)

        identity_row = QWidget(parent=self._private_fields)
        identity_layout = QHBoxLayout(identity_row)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(8)
        identity_layout.addWidget(self._identity_file_input, 1)
        identity_layout.addWidget(self._identity_file_browse_button)
        private_form.addRow(self._identity_file_label, identity_row)
        private_form.addRow(self._pinned_host_key_label, self._pinned_host_key_input)
        layout.addWidget(self._private_fields)

        status_form = QFormLayout()
        status_form.setSpacing(6)
        status_form.addRow(self._condition_label, self._condition_value)
        status_form.addRow(self._phase_label, self._phase_value)
        status_form.addRow(self._error_code_label, self._error_code_value)
        layout.addLayout(status_form)
        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addWidget(self._install_button)
        actions.addWidget(self._repair_button)
        actions.addWidget(self._remove_button)
        actions.addStretch(1)
        actions.addWidget(self._close_button)
        layout.addLayout(actions)

    def _wire_events(self) -> None:
        self._local_linux_radio.toggled.connect(self._sync_placement_fields)
        self._identity_file_browse_button.clicked.connect(self._choose_identity_file)
        self._install_button.clicked.connect(self._start_install)
        self._repair_button.clicked.connect(self._start_repair)
        self._remove_button.clicked.connect(self._start_remove)
        self._close_button.clicked.connect(self.close)

    def _sync_placement_fields(self) -> None:
        self._private_fields.setVisible(
            not self._retirement_only and self._private_ssh_radio.isChecked()
        )

    def _choose_identity_file(self) -> None:
        if self._shutdown or self._operation_active or self._retirement_request_active:
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
        ):
            return
        request = self._install_request()
        if self._task_runner.start_install(request):
            self._session_installation_id = request.installation_id
            self._begin_operation(AmdGuidedOperation.INSTALL)

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

    def _start_remove(self) -> None:
        if (
            self._shutdown
            or self._retirement_request_active
        ):
            return
        installation_id = self._session_installation_id or self._installation_id_input.text().strip()
        if not installation_id:
            return
        if self._task_runner.start_remove(installation_id):
            self._session_installation_id = installation_id
            self._retirement_request_active = True
            self._condition = "working"
            self._phase = "retirement_requesting"
            self._error_code = None
            self._render_status()
            self._sync_controls()

    def _install_request(self) -> AmdGuidedInstallRequest:
        placement = (
            AmdGuidedPlacement.PRIVATE_SSH
            if self._private_ssh_radio.isChecked()
            else AmdGuidedPlacement.LOCAL_LINUX
        )
        if placement is AmdGuidedPlacement.LOCAL_LINUX:
            return AmdGuidedInstallRequest(
                installation_id=self._installation_id_input.text().strip(),
                placement=placement,
                target_id=None,
                host=None,
                user=None,
                port=None,
                identity_file=None,
                pinned_host_key=None,
            )
        identity_value = self._identity_file_input.text().strip()
        return AmdGuidedInstallRequest(
            installation_id=self._installation_id_input.text().strip(),
            placement=placement,
            target_id=self._target_id_input.text().strip(),
            host=self._host_input.text().strip(),
            user=self._user_input.text().strip(),
            port=self._port_input.value(),
            identity_file=Path(identity_value) if identity_value else None,
            pinned_host_key=self._pinned_host_key_input.text().strip(),
        )

    def _begin_operation(self, operation: AmdGuidedOperation) -> None:
        self._operation_active = True
        self._condition = "working"
        self._phase = operation.value
        self._error_code = None
        self._render_status()
        self._sync_controls()

    def _finish_operation(self, result: object) -> None:
        if self._shutdown:
            return
        self._operation_active = False
        if self._retirement_request_active or self._retirement_requested:
            self._sync_controls()
            return
        if not isinstance(result, AmdGuidedTaskResult):
            self._condition = "failed"
            self._phase = "failed"
            self._error_code = "amd_operation_failed"
        else:
            self._condition = result.condition
            self._phase = result.phase
            self._error_code = result.error_code
            if result.operation is AmdGuidedOperation.INSTALL and result.succeeded:
                self._session_installation_id = result.installation_id
        self._render_status()
        self._sync_controls()

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
            # A later retry failure cannot resurrect installation controls after
            # the first durable Remove acknowledgement.  The only permissible
            # next action is another forward retirement attempt.
            self._retirement_requested = self._retirement_requested or result.succeeded
        self._render_status()
        self._sync_controls()

    def _sync_controls(self) -> None:
        editable = (
            not self._shutdown
            and not self._operation_active
            and not self._retirement_request_active
            and not self._retirement_requested
        )
        for widget in (
            self._local_linux_radio,
            self._private_ssh_radio,
            self._target_id_input,
            self._host_input,
            self._user_input,
            self._port_input,
            self._identity_file_input,
            self._identity_file_browse_button,
            self._pinned_host_key_input,
        ):
            widget.setEnabled(editable and not self._retirement_only)
        self._installation_id_input.setEnabled(editable)
        self._install_button.setVisible(not self._retirement_only)
        self._repair_button.setVisible(not self._retirement_only)
        self._install_button.setEnabled(editable and not self._retirement_only)
        can_repair_session = (
            editable
            and not self._retirement_only
            and self._session_installation_id is not None
            and self._condition != "removed"
        )
        self._repair_button.setEnabled(can_repair_session)
        self._remove_button.setEnabled(
            not self._shutdown
            and not self._retirement_request_active
            and (self._session_installation_id is not None or self._retirement_only)
            and self._condition != "removed"
        )
        self._close_button.setEnabled(not self._shutdown)

    def _render_status(self) -> None:
        self._condition_value.setText(self._status_value(self._condition))
        self._phase_value.setText(self._status_value(self._phase))
        self._error_code_value.setText(self._status_value(self._error_code))

    def _status_value(self, value: str | None) -> str:
        if value == "retirement_requesting":
            return self.tr("Requesting safe retirement")
        if value == "retirement_requested":
            return self.tr("Removal requested; retiring safely")
        return value if value is not None else self.tr("Not available")


def _new_installation_id() -> str:
    return f"amd-installation-{uuid4().hex}"


def _new_target_id() -> str:
    return f"amd-target-{uuid4().hex}"


__all__ = ["AmdGuidedSetupContribution", "AmdGuidedSetupDialog"]
