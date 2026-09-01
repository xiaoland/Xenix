"""Settings dialog: tab composition and the cross-card save flow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...config import AppPaths
from ...i18n import TranslationManager
from ...services.embedding_service import EmbeddingSettingsService
from ...services.knowledge_index_service import (
    KnowledgeIndexKind,
    KnowledgeIndexService,
)
from ...services.llm import (
    LLMService,
    LLMSettings,
    LLMSettingsService,
)
from ...services.ml.worker_settings import MLWorkerSettingsService
from ...services.paddle_ocr_service import PaddleOcrDeploymentService
from ...services.update_service import UpdateService
from ..about_dialog import AboutDialog
from ..semantic_identity import identify
from ._card import Card
from .contracts import SettingsTab
from .embedding import EmbeddingSettings
from .index_status import KnowledgeIndexStatus
from .ml_workers import MLWorkers
from .ocr import OcrSettings
from .provider import ProviderSettingsEditor


class SettingsDialog(QDialog):
    agent_settings_saved = Signal()
    embedding_settings_saved = Signal()
    ml_worker_settings_saved = Signal()
    software_update_requested = Signal()

    def __init__(
        self,
        paths: AppPaths,
        log_path: Path,
        db_path: Path,
        translation_manager: TranslationManager,
        llm_service: LLMService,
        llm_settings_service: LLMSettingsService,
        ml_worker_settings_service: MLWorkerSettingsService,
        embedding_settings_service: EmbeddingSettingsService,
        update_service: UpdateService | None = None,
        paddle_ocr_deployment: PaddleOcrDeploymentService | None = None,
        knowledge_index_service: KnowledgeIndexService | None = None,
        ssh_worker_setup: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._log_path = log_path
        self._db_path = db_path
        self._translation_manager = translation_manager
        self._llm_settings_service = llm_settings_service
        self._embedding_settings_service = embedding_settings_service
        self._software_updates_available = update_service is not None
        self._update_operation_active = False
        self._knowledge_index_service = knowledge_index_service
        self._about_dialog: AboutDialog | None = None
        self._shutdown = False

        self._language_label = QLabel()
        self._language_selector = QComboBox()
        self._about_button = QPushButton()
        self._save_button = QPushButton()

        self._tabs = QTabWidget()
        self._provider_editor = ProviderSettingsEditor(LLMSettings(), parent=self)

        self._embedding_card = Card()
        self._embedding_settings = EmbeddingSettings()
        self._embedding_card.set_content(self._embedding_settings)

        self._ocr_card = Card()
        self._ocr_settings = OcrSettings(paddle_ocr_deployment)
        self._ocr_card.set_content(self._ocr_settings)

        self._index_card = Card()
        self._index_status = KnowledgeIndexStatus(knowledge_index_service)
        self._index_card.set_content(self._index_status)

        self._ml_workers_card = Card()
        self._ml_workers = MLWorkers(
            ml_worker_settings_service,
            ssh_worker_setup_allowed=ssh_worker_setup,
        )
        self._ml_workers_card.set_content(self._ml_workers)

        self._tab_indexes: dict[SettingsTab, int] = {}
        self._assign_semantic_identities()

        self.resize(760, 760)
        self._build_ui()
        self._wire_events()
        self._load_agent_settings()
        self._load_embedding_settings()
        self.retranslate_ui()

    def _assign_semantic_identities(self) -> None:
        identify(self._language_selector, "settings.general.language")
        identify(self._about_button, "settings.about.open")
        identify(self._save_button, "settings.save")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header_layout.addWidget(self._language_label)
        header_layout.addWidget(self._language_selector)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)
        scroll.setWidget(scroll_content)

        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setContentsMargins(12, 12, 12, 12)
        ai_layout.setSpacing(16)
        ai_layout.addWidget(self._provider_editor)
        ai_layout.addStretch(1)

        knowledge_tab = QWidget()
        knowledge_layout = QVBoxLayout(knowledge_tab)
        knowledge_layout.setContentsMargins(12, 12, 12, 12)
        knowledge_layout.setSpacing(16)
        knowledge_layout.addWidget(self._embedding_card)
        knowledge_layout.addWidget(self._ocr_card)
        knowledge_layout.addWidget(self._index_card)
        knowledge_layout.addStretch(1)

        ml_workers_tab = QWidget()
        ml_workers_layout = QVBoxLayout(ml_workers_tab)
        ml_workers_layout.setContentsMargins(12, 12, 12, 12)
        ml_workers_layout.setSpacing(16)
        ml_workers_layout.addWidget(self._ml_workers_card)
        ml_workers_layout.addStretch(1)

        self._tab_indexes = {
            SettingsTab.AI: self._tabs.addTab(ai_tab, ""),
            SettingsTab.KNOWLEDGE_BASE: self._tabs.addTab(knowledge_tab, ""),
            SettingsTab.ML_WORKERS: self._tabs.addTab(ml_workers_tab, ""),
        }
        scroll_layout.addWidget(self._tabs)
        scroll_layout.addStretch(1)
        layout.addWidget(scroll, 1)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self._about_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._save_button)
        layout.addLayout(actions_layout)

    def _wire_events(self) -> None:
        self._about_button.clicked.connect(self._open_about_dialog)
        self._language_selector.currentIndexChanged.connect(self._on_language_changed)
        self._save_button.clicked.connect(self._save_agent_settings)
        self._ml_workers.worker_saved.connect(self.ml_worker_settings_saved.emit)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))
        self._tabs.setTabText(self._tab_indexes[SettingsTab.AI], self.tr("AI"))
        self._tabs.setTabText(
            self._tab_indexes[SettingsTab.KNOWLEDGE_BASE],
            self.tr("Knowledge Base"),
        )
        self._tabs.setTabText(
            self._tab_indexes[SettingsTab.ML_WORKERS],
            self.tr("ML Workers"),
        )
        self._provider_editor.retranslate_ui()
        self._embedding_settings.retranslate_ui()
        self._ocr_settings.retranslate_ui()
        self._index_status.retranslate_ui()
        self._ml_workers.retranslate_ui()
        self._about_button.setText(self.tr("About"))
        self._save_button.setText(self.tr("Save"))
        self._reload_language_options()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def show_tab(self, tab: SettingsTab) -> None:
        self._tabs.setCurrentIndex(self._tab_indexes[SettingsTab(tab)])

    def showEvent(self, event) -> None:
        if self._shutdown:
            super().showEvent(event)
            self.hide()
            return
        self._ocr_settings.activate()
        self._index_status.activate()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._deactivate()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._deactivate()
        super().closeEvent(event)

    def _deactivate(self) -> None:
        self._ocr_settings.deactivate()
        self._index_status.deactivate()

    def shutdown(self) -> None:
        """Quiesce UI-owned OCR tasks before their application services close."""
        if self._shutdown:
            return
        self._shutdown = True
        self._deactivate()
        self._ocr_settings.shutdown()
        self._index_status.shutdown()

    def _reload_language_options(self) -> None:
        current_locale = self._translation_manager.current_locale()
        labels = {
            "en_US": self.tr("English"),
            "zh_CN": self.tr("Simplified Chinese"),
        }
        self._language_selector.blockSignals(True)
        self._language_selector.clear()
        for locale_code in self._translation_manager.supported_locales():
            self._language_selector.addItem(labels[locale_code], locale_code)
        index = self._language_selector.findData(current_locale)
        if index >= 0:
            self._language_selector.setCurrentIndex(index)
        self._language_selector.blockSignals(False)

    def _on_language_changed(self, _index: int) -> None:
        locale_code = self._language_selector.currentData()
        if locale_code is None:
            return
        try:
            self._translation_manager.set_locale(str(locale_code))
            self.retranslate_ui()
            if self._about_dialog is not None:
                self._about_dialog.retranslate_ui()
        except Exception as exc:
            self._reload_language_options()
            QMessageBox.critical(
                self,
                self.tr("Language Switch Failed"),
                self.tr("Unable to switch the application language.\n\n{details}").format(details=str(exc)),
            )

    def _open_about_dialog(self) -> None:
        if self._about_dialog is None:
            self._about_dialog = AboutDialog(
                paths=self._paths,
                log_path=self._log_path,
                db_path=self._db_path,
                software_updates_available=self._software_updates_available,
                parent=self,
            )
            self._about_dialog.software_update_requested.connect(
                self.software_update_requested.emit
            )
            self._about_dialog.set_update_operation_active(
                self._update_operation_active
            )
        self._about_dialog.show()
        self._about_dialog.raise_()
        self._about_dialog.activateWindow()

    def set_update_operation_active(self, active: bool) -> None:
        self._update_operation_active = active
        if self._about_dialog is not None:
            self._about_dialog.set_update_operation_active(active)

    def _load_agent_settings(self) -> None:
        self._provider_editor.load_settings(self._llm_settings_service.load())

    def _load_embedding_settings(self) -> None:
        self._embedding_settings.load_settings(self._embedding_settings_service.load())

    def _save_agent_settings(self) -> None:
        rebuild_choice = "none"
        try:
            llm_settings = self._provider_editor.current_settings()
            embedding_settings = self._embedding_settings.current_settings()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        try:
            confirmation_required = (
                self._knowledge_index_service is not None
                and self._knowledge_index_service.embedding_change_requires_confirmation(
                    self._embedding_settings.snapshot,
                    embedding_settings,
                )
            )
        except Exception:
            QMessageBox.warning(
                self,
                self.tr("Knowledge Indexes"),
                self.tr("Knowledge index status is unavailable"),
            )
            return
        if confirmation_required:
            rebuild_choice = self._confirm_embedding_compatibility_change()
            if rebuild_choice == "cancel":
                return
        try:
            self._llm_settings_service.save(llm_settings)
            self._embedding_settings_service.save(embedding_settings)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        self._embedding_settings.load_settings(embedding_settings)
        self.agent_settings_saved.emit()
        self.embedding_settings_saved.emit()
        if rebuild_choice == "rebuild" and self._knowledge_index_service is not None:
            try:
                self._knowledge_index_service.enqueue_rebuild(
                    (KnowledgeIndexKind.TEXT_VECTOR,),
                    trigger="settings_change",
                )
            except Exception:
                QMessageBox.warning(
                    self,
                    self.tr("Knowledge Indexes"),
                    self.tr(
                        "Embedding settings were saved, but the vector rebuild "
                        "could not be queued."
                    ),
                )
        self._index_status.refresh()

    def _confirm_embedding_compatibility_change(self) -> str:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle(self.tr("Rebuild text vectors?"))
        message.setText(
            self.tr(
                "This change uses a different embedding space. Existing text "
                "vectors cannot be reused for current Knowledge content."
            )
        )
        rebuild = message.addButton(
            self.tr("Save and rebuild now"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        save_only = message.addButton(
            self.tr("Save; rebuild later"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel = message.addButton(QMessageBox.StandardButton.Cancel)
        message.setDefaultButton(rebuild)
        message.exec()
        selected = message.clickedButton()
        if selected is rebuild:
            return "rebuild"
        if selected is save_only:
            return "later"
        if selected is cancel:
            return "cancel"
        return "cancel"
