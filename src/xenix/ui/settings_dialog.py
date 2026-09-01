from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppPaths
from ..i18n import TranslationManager
from ..services.embedding_service import EmbeddingSettings, EmbeddingSettingsService
from ..services.llm import (
    LLMService,
    LLMSettings,
    LLMSettingsService,
)
from ..services.ml.worker_settings import MLWorkerKind, MLWorkerSettingsService
from ..services.knowledge_index_service import (
    KnowledgeIndexKind,
    KnowledgeIndexOverview,
    KnowledgeIndexService,
)
from ..services.paddle_ocr_service import (
    PaddleOcrDeploymentService,
)
from ..services.update_service import UpdateService
from .about_dialog import AboutDialog
from .knowledge_index_status import KnowledgeIndexStatusRequest
from .knowledge_index_ui import KnowledgeIndexRebuildDialog
from .semantic_identity import identify
from .settings.contracts import SettingsTab
from .settings.ocr import OcrSettingsCard
from .settings.provider import ProviderSettingsEditor
from .ssh_worker_setup_wizard import SshWorkerSetupWizard


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
        self._llm_service = llm_service
        self._llm_settings_service = llm_settings_service
        self._embedding_settings_service = embedding_settings_service
        self._ml_worker_settings_service = ml_worker_settings_service
        self._ssh_worker_setup_allowed = ssh_worker_setup
        self._software_updates_available = update_service is not None
        self._update_operation_active = False
        self._paddle_ocr_deployment = paddle_ocr_deployment
        self._knowledge_index_service = knowledge_index_service
        self._embedding_settings_snapshot = EmbeddingSettings()
        self._ssh_worker_wizard: SshWorkerSetupWizard | None = None
        self._about_dialog: AboutDialog | None = None
        self._shutdown = False
        self._lifecycle_generation = 0
        self._active = False
        self._cached_index_status: KnowledgeIndexOverview | None = None
        self._index_status_request: KnowledgeIndexStatusRequest | None = None
        self._index_status_failed = False
        self._index_status_refresh_pending = False
        self._index_dialog: KnowledgeIndexRebuildDialog | None = None
        self._index_refresh_timer = QTimer(self)
        self._index_refresh_timer.setInterval(1_000)
        self._index_refresh_timer.setSingleShot(True)
        self._index_refresh_timer.timeout.connect(self._schedule_index_status_probe)

        self._language_label = QLabel()
        self._language_selector = QComboBox()
        self._about_button = QPushButton()
        self._save_button = QPushButton()

        self._tabs = QTabWidget()
        self._embedding_card = QFrame()
        self._embedding_card.setFrameShape(QFrame.StyledPanel)
        self._embedding_card_layout = QFormLayout(self._embedding_card)
        self._embedding_card_layout.setContentsMargins(12, 12, 12, 12)

        self._index_card = QFrame()
        self._index_card.setFrameShape(QFrame.StyledPanel)
        self._index_card_layout = QFormLayout(self._index_card)
        self._index_card_layout.setContentsMargins(12, 12, 12, 12)

        self._ml_workers_card = QFrame()
        self._ml_workers_card.setFrameShape(QFrame.StyledPanel)
        self._ml_workers_card_layout = QFormLayout(self._ml_workers_card)
        self._ml_workers_card_layout.setContentsMargins(12, 12, 12, 12)

        self._embedding_title_label = QLabel()
        self._embedding_enabled_label = QLabel()
        self._embedding_base_url_label = QLabel()
        self._embedding_api_key_label = QLabel()
        self._embedding_model_label = QLabel()
        self._embedding_dimensions_label = QLabel()
        self._embedding_batch_size_label = QLabel()
        self._embedding_timeout_label = QLabel()

        self._index_title_label = QLabel()
        self._index_status_label = QLabel()
        self._index_status_label.setWordWrap(True)
        self._index_rebuild_button = QPushButton()

        self._ml_workers_title_label = QLabel()
        self._ml_workers_summary_label = QLabel()
        self._ml_workers_setup_button = QPushButton()

        self._provider_editor = ProviderSettingsEditor(
            LLMSettings(), parent=self
        )
        self._ocr_settings_card = OcrSettingsCard(
            self._paddle_ocr_deployment, parent=self
        )

        self._embedding_enabled_checkbox = QCheckBox()
        self._embedding_base_url_input = QLineEdit()
        self._embedding_api_key_input = QLineEdit()
        self._embedding_api_key_input.setEchoMode(QLineEdit.Password)
        self._embedding_model_input = QLineEdit()
        self._embedding_dimensions_input = QSpinBox()
        self._embedding_dimensions_input.setRange(0, 65_536)
        self._embedding_batch_size_input = QSpinBox()
        self._embedding_batch_size_input.setRange(1, 2_048)
        self._embedding_timeout_input = QSpinBox()
        self._embedding_timeout_input.setRange(1, 3_600)
        self._embedding_timeout_input.setSuffix(" s")
        self._tab_indexes: dict[SettingsTab, int] = {}
        self._assign_semantic_identities()

        self.resize(760, 760)
        self._build_ui()
        self._wire_events()
        if not self._ssh_worker_setup_allowed:
            self._ml_workers_setup_button.setEnabled(False)
        self._load_agent_settings()
        self._load_embedding_settings()
        self.retranslate_ui()

    def _assign_semantic_identities(self) -> None:
        identities = (
            (self._language_selector, "settings.general.language"),
            (self._about_button, "settings.about.open"),
            (self._save_button, "settings.save"),
            (self._index_rebuild_button, "settings.knowledge.indexes.rebuild"),
            (self._ml_workers_setup_button, "settings.ml-workers.add-ssh"),
            (self._embedding_enabled_checkbox, "settings.embedding.enabled"),
            (self._embedding_base_url_input, "settings.embedding.base-url"),
            (self._embedding_api_key_input, "settings.embedding.api-key"),
            (self._embedding_model_input, "settings.embedding.model"),
            (self._embedding_dimensions_input, "settings.embedding.dimensions"),
            (self._embedding_batch_size_input, "settings.embedding.batch-size"),
            (self._embedding_timeout_input, "settings.embedding.timeout"),
        )
        for widget, semantic_id in identities:
            identify(widget, semantic_id)

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
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)
        scroll.setWidget(scroll_content)

        self._embedding_card_layout.addRow(self._embedding_title_label)
        self._embedding_card_layout.addRow(self._embedding_enabled_label, self._embedding_enabled_checkbox)
        self._embedding_card_layout.addRow(self._embedding_base_url_label, self._embedding_base_url_input)
        self._embedding_card_layout.addRow(self._embedding_api_key_label, self._embedding_api_key_input)
        self._embedding_card_layout.addRow(self._embedding_model_label, self._embedding_model_input)
        self._embedding_card_layout.addRow(self._embedding_dimensions_label, self._embedding_dimensions_input)
        self._embedding_card_layout.addRow(self._embedding_batch_size_label, self._embedding_batch_size_input)
        self._embedding_card_layout.addRow(self._embedding_timeout_label, self._embedding_timeout_input)

        self._index_card_layout.addRow(self._index_title_label)
        self._index_card_layout.addRow(self._index_status_label)
        self._index_card_layout.addRow(self._index_rebuild_button)

        self._ml_workers_summary_label.setWordWrap(True)
        self._ml_workers_card_layout.addRow(self._ml_workers_title_label)
        self._ml_workers_card_layout.addRow(self._ml_workers_summary_label)
        self._ml_workers_card_layout.addRow(self._ml_workers_setup_button)

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
        knowledge_layout.addWidget(self._ocr_settings_card)
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
        self._ml_workers_setup_button.clicked.connect(self._open_ssh_worker_wizard)
        self._index_rebuild_button.clicked.connect(self._open_index_rebuild)

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
        self._embedding_title_label.setText(self.tr("Embedding provider"))
        self._embedding_enabled_label.setText(self.tr("Enabled"))
        self._embedding_base_url_label.setText(self.tr("Base URL"))
        self._embedding_api_key_label.setText(self.tr("API key"))
        self._embedding_model_label.setText(self.tr("Model"))
        self._embedding_dimensions_label.setText(self.tr("Dimensions"))
        self._embedding_dimensions_input.setSpecialValueText(self.tr("Provider default (0)"))
        self._embedding_batch_size_label.setText(self.tr("Batch size"))
        self._embedding_timeout_label.setText(self.tr("Timeout"))
        self._index_title_label.setText(self.tr("Indexes"))
        self._index_rebuild_button.setText(self.tr("Rebuild indexes..."))
        self._provider_editor.retranslate_ui()
        self._ml_workers_title_label.setText(self.tr("ML workers"))
        self._ml_workers_setup_button.setText(self.tr("Add SSH worker..."))
        self._about_button.setText(self.tr("About"))
        self._save_button.setText(self.tr("Save"))
        self._reload_language_options()
        self._refresh_ml_worker_summary()
        self._ocr_settings_card.retranslate_ui()
        self._render_index_status()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def show_tab(self, tab: SettingsTab) -> None:
        self._tabs.setCurrentIndex(self._tab_indexes[SettingsTab(tab)])

    def showEvent(self, event) -> None:
        if self._shutdown:
            super().showEvent(event)
            self.hide()
            return
        self._active = True
        self._lifecycle_generation += 1
        self._ocr_settings_card.activate()
        self._render_index_status()
        super().showEvent(event)
        self._request_index_status_refresh(delay_ms=0)

    def hideEvent(self, event) -> None:
        self._deactivate()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._deactivate()
        super().closeEvent(event)

    def _deactivate(self) -> None:
        if self._active:
            self._lifecycle_generation += 1
        self._active = False
        self._ocr_settings_card.deactivate()
        self._index_refresh_timer.stop()
        self._index_status_refresh_pending = False
        if self._index_status_request is not None:
            self._index_status_request.cancel()
        if self._index_dialog is not None:
            self._index_dialog.hide()

    def shutdown(self) -> None:
        """Quiesce UI-owned OCR tasks before their application services close."""
        if self._shutdown:
            return
        self._shutdown = True
        self._deactivate()
        self._ocr_settings_card.shutdown()

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
        settings = self._embedding_settings_service.load()
        self._embedding_settings_snapshot = settings.model_copy(deep=True)
        self._embedding_enabled_checkbox.setChecked(settings.enabled)
        self._embedding_base_url_input.setText(settings.base_url)
        self._embedding_api_key_input.setText(settings.api_key)
        self._embedding_model_input.setText(settings.model)
        self._embedding_dimensions_input.setValue(settings.dimensions or 0)
        self._embedding_batch_size_input.setValue(settings.batch_size)
        self._embedding_timeout_input.setValue(settings.timeout_seconds)

    def _save_agent_settings(self) -> None:
        rebuild_choice = "none"
        try:
            llm_settings = self._provider_editor.current_settings()
            embedding_settings = self._embedding_settings_from_fields()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Settings"), str(exc))
            return
        try:
            confirmation_required = (
                self._knowledge_index_service is not None
                and self._knowledge_index_service.embedding_change_requires_confirmation(
                    self._embedding_settings_snapshot,
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
        self._embedding_settings_snapshot = embedding_settings.model_copy(deep=True)
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
        self._request_index_status_refresh()

    def _confirm_embedding_compatibility_change(self) -> str:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Warning)
        message.setWindowTitle(self.tr("Rebuild text vectors?"))
        message.setText(
            self.tr(
                "This change uses a different embedding space. Existing text "
                "vectors cannot be reused for current Knowledge content."
            )
        )
        rebuild = message.addButton(
            self.tr("Save and rebuild now"),
            QMessageBox.AcceptRole,
        )
        save_only = message.addButton(
            self.tr("Save; rebuild later"),
            QMessageBox.ActionRole,
        )
        cancel = message.addButton(QMessageBox.Cancel)
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

    def _embedding_settings_from_fields(self) -> EmbeddingSettings:
        dimensions = self._embedding_dimensions_input.value()
        current = self._embedding_settings_snapshot
        return EmbeddingSettings(
            schema_version=current.schema_version,
            enabled=self._embedding_enabled_checkbox.isChecked(),
            provider_key=current.provider_key,
            dialect=current.dialect,
            base_url=self._embedding_base_url_input.text(),
            api_key=self._embedding_api_key_input.text(),
            model=self._embedding_model_input.text(),
            dimensions=dimensions or None,
            batch_size=self._embedding_batch_size_input.value(),
            timeout_seconds=self._embedding_timeout_input.value(),
        )

    def _open_index_rebuild(self) -> None:
        if self._knowledge_index_service is None:
            return
        if self._index_dialog is None:
            self._index_dialog = KnowledgeIndexRebuildDialog(
                self._knowledge_index_service,
                self,
            )
            self._index_dialog.submitted.connect(
                lambda _task_id: self._request_index_status_refresh()
            )
        self._index_dialog.open()

    def _request_index_status_refresh(self, *, delay_ms: int = 0) -> None:
        if self._shutdown or not self._active or self._knowledge_index_service is None:
            return
        if self._index_status_request is not None:
            self._index_status_refresh_pending = True
            return
        if self._cached_index_status is None:
            self._index_status_failed = False
            self._render_index_status()
        self._index_refresh_timer.start(max(0, delay_ms))

    def _schedule_index_status_probe(self) -> None:
        if self._shutdown or not self._active or self._knowledge_index_service is None:
            return
        if self._index_status_request is not None:
            self._index_status_refresh_pending = True
            return
        generation = self._lifecycle_generation
        request = KnowledgeIndexStatusRequest(generation)
        request.finished.connect(
            self._on_index_status_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        self._index_status_request = request
        request.start(self._knowledge_index_service)

    def _on_index_status_finished(
        self,
        request: object,
        generation: int,
        result: object,
    ) -> None:
        if request is not self._index_status_request:
            return
        self._index_status_request = None
        if self._shutdown:
            return
        if generation != self._lifecycle_generation or not self._active:
            if self._active:
                self._index_status_refresh_pending = False
                self._request_index_status_refresh()
            return

        refresh_pending = self._index_status_refresh_pending
        self._index_status_refresh_pending = False
        if refresh_pending:
            self._request_index_status_refresh()
            return

        if isinstance(result, KnowledgeIndexOverview):
            self._cached_index_status = result
            self._index_status_failed = False
        else:
            self._cached_index_status = None
            self._index_status_failed = True
        self._render_index_status()

        if (
            isinstance(result, KnowledgeIndexOverview)
            and result.active_task_status in {"queued", "running"}
        ):
            self._request_index_status_refresh(delay_ms=1_000)

    def _render_index_status(self) -> None:
        if self._knowledge_index_service is None:
            self._index_status_label.setText(
                self.tr("Knowledge index service is unavailable")
            )
            self._index_rebuild_button.setEnabled(False)
            return
        status = self._cached_index_status
        if status is None:
            text = (
                self.tr("Knowledge index status is unavailable")
                if self._index_status_failed
                else self.tr("Checking Knowledge index status")
            )
            self._index_status_label.setText(text)
            self._index_rebuild_button.setEnabled(False)
            return
        self._index_status_label.setText(
            self.tr("Keyword: %1\nText vectors: %2")
            .replace("%1", self._translated_index_state(status.keyword_state))
            .replace(
                "%2", self._translated_index_state(status.text_vector_state)
            )
        )
        self._index_rebuild_button.setEnabled(status.unit_count > 0)

    def _translated_index_state(self, state: str) -> str:
        translations = {
            "ready": self.tr("Ready"),
            "building": self.tr("Building"),
            "needs_rebuild": self.tr("Needs rebuild"),
            "unavailable": self.tr("Unavailable"),
            "needs_attention": self.tr("Needs attention"),
        }
        return translations.get(state, self.tr("Unknown status"))

    def _refresh_ml_worker_summary(self) -> None:
        settings = self._ml_worker_settings_service.load()
        enabled = [worker for worker in settings.workers if worker.enabled]
        local_count = sum(1 for worker in enabled if worker.kind is MLWorkerKind.LOCAL)
        ssh_count = sum(1 for worker in enabled if worker.kind is MLWorkerKind.SSH)
        total_slots = sum(worker.max_concurrent_tasks for worker in enabled)
        self._ml_workers_summary_label.setText(
            self.tr("{local_count} local, {ssh_count} SSH, {slots} execution slot(s).").format(
                local_count=local_count,
                ssh_count=ssh_count,
                slots=total_slots,
            )
        )

    def _open_ssh_worker_wizard(self) -> None:
        # An agent-safe profile denies SSH worker setup at the composition seam:
        # constructing the wizard (and its SshWorkerSetupService) would let it
        # write ~/.ssh/config and run ssh/scp. Refuse here rather than hiding the
        # side-effect entry in a lower layer.
        if not self._ssh_worker_setup_allowed:
            return
        wizard = SshWorkerSetupWizard(
            self._ml_worker_settings_service,
            parent=self,
        )
        wizard.worker_saved.connect(self._refresh_ml_worker_summary)
        wizard.worker_saved.connect(self.ml_worker_settings_saved.emit)
        self._ssh_worker_wizard = wizard
        wizard.show()
        wizard.raise_()
        wizard.activateWindow()


__all__ = ["AboutDialog", "SettingsDialog", "SettingsTab"]
