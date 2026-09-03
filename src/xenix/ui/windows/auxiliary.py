"""Lifecycle coordinator for windows opened from the main shell.

The coordinator deliberately knows window factories, not application services.
This keeps production composition explicit while allowing the shell to request a
small set of window operations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeAlias

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from ..settings.contracts import SettingsTab

if TYPE_CHECKING:
    from ..job_center import JobCenterDialog
    from ..knowledge_workspace import KnowledgeWorkspaceDialog
    from ..settings_dialog import SettingsDialog
    from ..software_update import SoftwareUpdateController
    from ..tool_call_detail_view import ToolCallDetailView


SettingsWindowFactory: TypeAlias = Callable[[QWidget], "SettingsDialog"]
KnowledgeWindowFactory: TypeAlias = Callable[
    [QWidget, Callable[[], None]], "KnowledgeWorkspaceDialog"
]
DetailWindowFactory: TypeAlias = Callable[[QWidget, list[str]], "ToolCallDetailView"]
JobCenterWindowFactory: TypeAlias = Callable[[QWidget], "JobCenterDialog"]


class AuxiliaryWindowCoordinator(QObject):
    """Own lazy auxiliary windows and their presentation-only wiring.

    It is parented to the shell as a QObject, so its timer and Qt connections die
    with the shell while the visible windows remain children of that shell.
    """

    settings_saved = Signal()

    def __init__(
        self,
        parent: QWidget,
        *,
        settings_factory: SettingsWindowFactory,
        knowledge_factory: KnowledgeWindowFactory | None,
        detail_factory: DetailWindowFactory,
        job_center_factory: JobCenterWindowFactory | None = None,
        update_controller: SoftwareUpdateController | None = None,
    ) -> None:
        super().__init__(parent)
        self._owner = parent
        self._settings_factory = settings_factory
        self._knowledge_factory = knowledge_factory
        self._detail_factory = detail_factory
        self._job_center_factory = job_center_factory
        self._update_controller = update_controller
        self._settings_dialog: SettingsDialog | None = None
        self._knowledge_dialog: KnowledgeWorkspaceDialog | None = None
        self._job_center_dialog: JobCenterDialog | None = None
        self._detail_views: list[ToolCallDetailView] = []
        self._shutdown = False
        self._auto_check_timer = QTimer(self)
        self._auto_check_timer.setSingleShot(True)
        self._auto_check_timer.timeout.connect(self._start_auto_check)
        if update_controller is not None and update_controller.can_auto_check:
            self._auto_check_timer.start(1_000)

    def show_settings(self, *, tab: SettingsTab = SettingsTab.AI) -> None:
        if self._shutdown:
            return
        dialog = self._settings_dialog
        if dialog is None:
            dialog = self._settings_factory(self._owner)
            self._settings_dialog = dialog
            dialog.agent_settings_saved.connect(self.settings_saved)
            dialog.destroyed.connect(self._forget_settings_dialog)
            self._wire_settings_updates(dialog)
        dialog.show_tab(tab)
        self._show_and_activate(dialog)

    def show_knowledge(self) -> None:
        if self._shutdown:
            return
        if self._knowledge_factory is None:
            QMessageBox.warning(
                self._owner,
                QCoreApplication.translate("MainWindow", "Knowledge Workspace"),
                QCoreApplication.translate(
                    "MainWindow", "Knowledge services are not available."
                ),
            )
            return
        dialog = self._knowledge_dialog
        if dialog is None:
            dialog = self._knowledge_factory(self._owner, self._open_knowledge_settings)
            self._knowledge_dialog = dialog
            dialog.destroyed.connect(self._forget_knowledge_dialog)
        self._show_and_activate(dialog)

    def show_jobs(self) -> None:
        if self._shutdown:
            return
        if self._job_center_factory is None:
            QMessageBox.warning(
                self._owner,
                QCoreApplication.translate("MainWindow", "Jobs"),
                QCoreApplication.translate("MainWindow", "Job services are not available."),
            )
            return
        dialog = self._job_center_dialog
        if dialog is None:
            dialog = self._job_center_factory(self._owner)
            self._job_center_dialog = dialog
            dialog.destroyed.connect(self._forget_job_center_dialog)
        self._show_and_activate(dialog)

    def show_tool_call_detail(self, *, task_ids: list[str]) -> None:
        if self._shutdown or not task_ids:
            return
        view = self._detail_factory(self._owner, task_ids)
        view.destroyed.connect(
            lambda _object=None, detail=view: self._forget_detail_view(detail)
        )
        self._detail_views.append(view)
        self._show_and_activate(view)

    def retranslate_ui(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.retranslate_ui()
        if self._knowledge_dialog is not None:
            self._knowledge_dialog.retranslate_ui()
        if self._job_center_dialog is not None:
            self._job_center_dialog.retranslate_ui()
        if self._update_controller is not None:
            self._update_controller.retranslate_ui()

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._auto_check_timer.stop()
        if self._update_controller is not None:
            self._update_controller.shutdown()
        if self._settings_dialog is not None:
            self._settings_dialog.shutdown()
        if self._knowledge_dialog is not None:
            self._knowledge_dialog.shutdown()
        if self._job_center_dialog is not None:
            self._job_center_dialog.shutdown()
        for view in tuple(self._detail_views):
            view.close()
            view.deleteLater()
        self._detail_views.clear()

    def _open_knowledge_settings(self) -> None:
        self.show_settings(tab=SettingsTab.KNOWLEDGE_BASE)

    def _wire_settings_updates(self, dialog: SettingsDialog) -> None:
        controller = self._update_controller
        if controller is None:
            return
        dialog.software_update_requested.connect(self._request_update)
        controller.operation_active_changed.connect(self._set_update_operation_active)
        dialog.set_update_operation_active(controller.active)

    def _request_update(self) -> None:
        if not self._shutdown and self._update_controller is not None:
            self._update_controller.request_update()

    def _set_update_operation_active(self, active: bool) -> None:
        if not self._shutdown and self._settings_dialog is not None:
            self._settings_dialog.set_update_operation_active(active)

    def _start_auto_check(self) -> None:
        if self._shutdown or self._update_controller is None:
            return
        self._update_controller.start_background_check()

    @staticmethod
    def _show_and_activate(window: QWidget) -> None:
        window.show()
        window.raise_()
        window.activateWindow()

    def _forget_detail_view(self, view: ToolCallDetailView) -> None:
        if view in self._detail_views:
            self._detail_views.remove(view)

    def _forget_settings_dialog(self, _object: object = None) -> None:
        self._settings_dialog = None

    def _forget_knowledge_dialog(self, _object: object = None) -> None:
        self._knowledge_dialog = None

    def _forget_job_center_dialog(self, _object: object = None) -> None:
        self._job_center_dialog = None
