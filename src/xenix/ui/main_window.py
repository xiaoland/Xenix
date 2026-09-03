from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.agent import AgentHarnessService
from ..services.artifact_service import ArtifactService
from ..services.link_router import LinkRouter
from ..services.llm import LLMService
from .chat_workspace import ChatWorkspace
from .chatbot import ThreadDetailView
from .conversation.execution import SubmissionExecutor
from .history import HistoryPanel, HistoryPort
from .layout_debug import dump_layout_if_enabled
from .native_widgets import emphasize_label
from .semantic_identity import identify
from .settings.contracts import SettingsTab
from .windows.auxiliary import AuxiliaryWindowCoordinator


class MainWindow(QMainWindow):
    """Application shell: window chrome, main-area layout, navigation, child lifecycle.

    Conversation orchestration lives in :class:`ChatWorkspace`; this window only
    constructs the child widgets, lays them out, and forwards top-level
    navigation.  That keeps ``HistoryPanel`` and ``ThreadDetailView`` buildable
    by the Widget Lab without instantiating the desktop service graph.
    """

    closing = Signal()

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
        self._auxiliary_windows = auxiliary_factory(self)
        self._auxiliary_windows.settings_saved.connect(self._reload_agent_provider)

        self._title_label = QLabel(parent=self)
        self._settings_button = QPushButton(parent=self)
        self._settings_button.clicked.connect(self._open_settings)
        self._knowledge_button = QPushButton(parent=self)
        self._knowledge_button.clicked.connect(self._open_knowledge_workspace)
        self._jobs_button = QPushButton(parent=self)
        self._jobs_button.clicked.connect(self._open_jobs)

        self._history_panel = HistoryPanel(
            history_port,
            is_thread_running=lambda thread_id: (
                self.conversation_thread_id == thread_id and not self.conversation_idle
            ),
            parent=self,
        )
        self._thread_detail_view = ThreadDetailView(parent=self)
        self._chat_workspace = ChatWorkspace(
            agent_harness_service=agent_harness_service,
            llm_service=llm_service,
            artifact_service=artifact_service,
            link_router=link_router,
            current_locale=current_locale,
            history_panel=self._history_panel,
            thread_detail_view=self._thread_detail_view,
            open_tool_call_detail=lambda task_ids: self._auxiliary_windows.show_tool_call_detail(
                task_ids=task_ids
            ),
            conversation_executor=conversation_executor,
            parent=self,
        )

        self._assign_semantic_identities()
        self.resize(1080, 760)
        self._setup_ui()
        self.retranslate_ui()
        self._chat_workspace.sync_model_options()

    # Public delegations (Widget Lab and headed harness) ---------------------

    @property
    def conversation_thread_id(self) -> str | None:
        return self._chat_workspace.conversation_thread_id

    @property
    def conversation_idle(self) -> bool:
        return self._chat_workspace.conversation_idle

    def refresh_history(self, *, selected_thread_id: str | None = None) -> None:
        self._chat_workspace.refresh_history(selected_thread_id=selected_thread_id)

    # Shell, layout, navigation ----------------------------------------------

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
        self._jobs_button.setMinimumWidth(72)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self._jobs_button)
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
        self._chat_workspace.open_initial_thread()
        dump_layout_if_enabled(root, reason="main-window-setup")

    def _assign_semantic_identities(self) -> None:
        identify(self._settings_button, "main.header.settings")
        identify(self._knowledge_button, "main.header.knowledge")
        identify(self._jobs_button, "main.header.jobs")

    def _open_settings(
        self,
        _checked: bool = False,
        *,
        tab: SettingsTab = SettingsTab.AI,
    ) -> None:
        self._auxiliary_windows.show_settings(tab=tab)

    def _open_knowledge_workspace(self) -> None:
        self._auxiliary_windows.show_knowledge()

    def _open_jobs(self) -> None:
        self._auxiliary_windows.show_jobs()

    def _reload_agent_provider(self) -> None:
        self._chat_workspace.sync_model_options()

    # Lifecycle --------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        super().closeEvent(event)
        if event.isAccepted():
            self._chat_workspace.shutdown()
            self._history_panel.shutdown()
            self._auxiliary_windows.shutdown()
            self.closing.emit()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Xenix Native"))
        self._title_label.setText(self.tr("Xenix"))
        self._settings_button.setText(self.tr("Settings"))
        self._knowledge_button.setText(self.tr("Knowledge"))
        self._jobs_button.setText(self.tr("Jobs"))
        self._history_panel.retranslate_ui()
        self._thread_detail_view.retranslate_ui()
        self._auxiliary_windows.retranslate_ui()
        self._chat_workspace.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
