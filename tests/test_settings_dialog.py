from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import TranslationManager
from xenix.services.embedding_service import EmbeddingSettings, EmbeddingSettingsService
from xenix.services.llm import LLMProviderConfig, LLMService, LLMSettings, LLMSettingsService
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.services.paddle_ocr_service import PaddleOcrState, PaddleOcrStatus
from xenix.ui.settings_dialog import SettingsDialog, SettingsTab


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_settings_dialog_provider_switch_preserves_distinct_provider_fields(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    llm_settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="bailian",
                    display_name="Bailian",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode",
                    api_key="bailian-secret",
                    models=["qwen-plus"],
                    timeout_seconds=60,
                ),
                LLMProviderConfig(
                    key="deepseek",
                    display_name="DeepSeek",
                    base_url="https://api.deepseek.com",
                    api_key="deepseek-secret",
                    models=["deepseek-chat"],
                    timeout_seconds=120,
                ),
                LLMProviderConfig(
                    key="kimi",
                    display_name="Kimi",
                    base_url="https://api.moonshot.cn/v1",
                    api_key="kimi-secret",
                    models=["kimi-k2"],
                    timeout_seconds=120,
                ),
            ],
            default_fq_model_key="bailian/qwen-plus",
            retry_attempts=4,
        )
    )
    translation_manager = TranslationManager(app, paths)
    translation_manager.set_locale("en_US", persist=False)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
        EmbeddingSettingsService(paths),
    )

    try:
        assert dialog._tabs.count() == 3
        assert dialog._tabs.tabText(0) == "AI"
        assert dialog._tabs.tabText(1) == "Knowledge Base"
        assert dialog._tabs.tabText(2) == "ML Workers"
        assert dialog._global_models_title_label.text() == "Global models"
        assert dialog._about_button.text() == "About"
        assert dialog._llm_retry_attempts_input.value() == 4

        dialog._provider_base_url_input.setText("https://edited-bailian.example.test")
        dialog._provider_api_key_input.setText("edited-bailian-secret")
        dialog._provider_models_input.setPlainText("edited-qwen\nedited-title")
        dialog._llm_retry_attempts_input.setValue(6)

        dialog._provider_selector.setCurrentIndex(dialog._provider_selector.findData("deepseek"))
        app.processEvents()

        assert dialog._provider_configs[0].base_url == "https://edited-bailian.example.test"
        assert dialog._provider_configs[0].api_key == "edited-bailian-secret"
        assert dialog._provider_configs[0].models == ["edited-qwen", "edited-title"]
        assert dialog._provider_configs[1].key == "deepseek"
        assert dialog._provider_configs[1].base_url == "https://api.deepseek.com"
        assert dialog._provider_key_input.text() == "deepseek"
        assert dialog._provider_base_url_input.text() == "https://api.deepseek.com"
        assert dialog._provider_models_input.toPlainText() == "deepseek-chat"
        assert _combo_values(dialog._llm_default_model_selector) == [
            "bailian/edited-qwen",
            "bailian/edited-title",
            "deepseek/deepseek-chat",
            "kimi/kimi-k2",
        ]

        dialog._save_agent_settings()
        loaded = llm_settings_service.load()

        assert [provider.key for provider in loaded.providers] == ["bailian", "deepseek", "kimi"]
        assert [provider.base_url for provider in loaded.providers] == [
            "https://edited-bailian.example.test",
            "https://api.deepseek.com",
            "https://api.moonshot.cn/v1",
        ]
        assert [provider.models for provider in loaded.providers] == [
            ["edited-qwen", "edited-title"],
            ["deepseek-chat"],
            ["kimi-k2"],
        ]
        assert loaded.retry_attempts == 6
    finally:
        dialog.close()


def test_settings_dialog_targets_knowledge_tab_and_runs_ocr_setup_off_ui_thread(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    import threading

    class Deployment:
        def __init__(self) -> None:
            self.status_thread_ids: list[int] = []
            self.install_thread_ids: list[int] = []

        def status(self):
            self.status_thread_ids.append(threading.get_ident())
            return PaddleOcrStatus(PaddleOcrState.NOT_INSTALLED)

        def install(self, progress):
            self.install_thread_ids.append(threading.get_ident())
            progress("downloading_bundle")
            progress("ready")
            return PaddleOcrStatus(PaddleOcrState.READY)

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    deployment = Deployment()
    translation_manager = TranslationManager(app, paths)
    translation_manager.set_locale("en_US", persist=False)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
        EmbeddingSettingsService(paths),
        paddle_ocr_deployment=deployment,
    )

    try:
        dialog.show_tab(SettingsTab.KNOWLEDGE_BASE)
        dialog.show()
        assert dialog._thread_pool.waitForDone(2_000)
        app.processEvents()
        assert dialog._tabs.currentIndex() == 1
        assert deployment.status_thread_ids
        assert all(value != threading.get_ident() for value in deployment.status_thread_ids)

        dialog._install_ocr()
        assert dialog._thread_pool.waitForDone(2_000)
        app.processEvents()
        assert deployment.install_thread_ids
        assert all(value != threading.get_ident() for value in deployment.install_thread_ids)
        assert dialog._ocr_status_label.text() == "Local PaddleOCR is ready"
    finally:
        dialog.close()


def test_embedding_space_change_confirmation_can_queue_or_cancel_rebuild(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    class Indexes:
        def __init__(self) -> None:
            self.enqueued: list[tuple[tuple[str, ...], str]] = []

        def embedding_change_requires_confirmation(self, previous, proposed):
            return previous.model != proposed.model and proposed.enabled

        def enqueue_rebuild(self, kinds, *, trigger):
            self.enqueued.append((tuple(str(kind) for kind in kinds), trigger))
            return "task-1"

        def status(self):
            return SimpleNamespace(
                keyword_state="ready",
                text_vector_state="needs_rebuild",
                unit_count=1,
            )

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    embeddings = EmbeddingSettingsService(paths)
    embeddings.save(
        EmbeddingSettings(
            enabled=True,
            base_url="https://embedding.example.test",
            model="meaning-v1",
        )
    )
    indexes = Indexes()
    translation_manager = TranslationManager(app, paths)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
        embeddings,
        knowledge_index_service=indexes,
    )

    try:
        monkeypatch.setattr(
            dialog,
            "_confirm_embedding_compatibility_change",
            lambda: "rebuild",
        )
        dialog._embedding_model_input.setText("meaning-v2")
        dialog._save_agent_settings()

        assert embeddings.load().model == "meaning-v2"
        assert indexes.enqueued == [(('text_vector',), "settings_change")]

        monkeypatch.setattr(
            dialog,
            "_confirm_embedding_compatibility_change",
            lambda: "cancel",
        )
        dialog._embedding_model_input.setText("meaning-v3")
        dialog._save_agent_settings()

        assert embeddings.load().model == "meaning-v2"
        assert indexes.enqueued == [(('text_vector',), "settings_change")]

        translation_manager.set_locale("zh_CN", persist=False)
        app.processEvents()
        assert dialog._index_status_label.text() == "关键词：就绪\n文本向量：需要重建"
        translation_manager.set_locale("en_US", persist=False)
        app.processEvents()
    finally:
        dialog.close()


def test_embedding_settings_are_not_saved_when_index_impact_is_unknown(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    class Indexes:
        def embedding_change_requires_confirmation(self, previous, proposed):
            raise RuntimeError("database unavailable")

        def status(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    embeddings = EmbeddingSettingsService(paths)
    embeddings.save(
        EmbeddingSettings(
            enabled=True,
            base_url="https://embedding.example.test",
            model="meaning-v1",
        )
    )
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    translation_manager = TranslationManager(app, paths)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
        embeddings,
        knowledge_index_service=Indexes(),
    )

    try:
        dialog._embedding_model_input.setText("meaning-v2")
        dialog._save_agent_settings()

        assert embeddings.load().model == "meaning-v1"
        assert warnings == [
            ("Knowledge Indexes", "Knowledge index status is unavailable")
        ]
    finally:
        dialog.close()


def test_settings_dialog_persists_embedding_settings_independently(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    llm_settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="chat",
                    display_name="Chat",
                    base_url="https://chat.example.test",
                    api_key="chat-secret",
                    models=["chat-model"],
                )
            ],
            default_fq_model_key="chat/chat-model",
        )
    )
    embedding_settings_service = EmbeddingSettingsService(paths)
    embedding_settings_service.save(
        EmbeddingSettings(
            enabled=True,
            provider_key="semantic",
            base_url="https://embedding.example.test/v1",
            api_key="embedding-secret",
            model="embedding-model",
            dimensions=768,
            batch_size=24,
            timeout_seconds=45,
        )
    )
    translation_manager = TranslationManager(app, paths)
    translation_manager.set_locale("en_US", persist=False)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
        embedding_settings_service=embedding_settings_service,
    )
    agent_saved: list[bool] = []
    embedding_saved: list[bool] = []
    dialog.agent_settings_saved.connect(lambda: agent_saved.append(True))
    dialog.embedding_settings_saved.connect(lambda: embedding_saved.append(True))

    try:
        assert dialog._embedding_title_label.text() == "Embedding provider"
        assert dialog._provider_base_url_input.text() == "https://chat.example.test"
        assert dialog._provider_api_key_input.text() == "chat-secret"
        assert dialog._embedding_base_url_input.text() == "https://embedding.example.test/v1"
        assert dialog._embedding_api_key_input.text() == "embedding-secret"
        assert dialog._embedding_api_key_input.echoMode() == QLineEdit.Password
        assert dialog._embedding_dimensions_input.value() == 768
        assert dialog._embedding_dimensions_input.specialValueText() == "Provider default (0)"

        dialog._embedding_model_input.setText("unsaved-model")
        translation_manager.set_locale("zh_CN", persist=False)
        app.processEvents()
        assert dialog._embedding_title_label.text() == "嵌入模型提供商"
        assert dialog._embedding_dimensions_label.text() == "向量维度"
        assert dialog._embedding_dimensions_input.specialValueText() == "使用提供商默认值（0）"
        assert dialog._embedding_model_input.text() == "unsaved-model"
        translation_manager.set_locale("en_US", persist=False)
        app.processEvents()

        dialog._embedding_enabled_checkbox.setChecked(False)
        dialog._embedding_base_url_input.setText("https://new-embedding.example.test")
        dialog._embedding_api_key_input.setText("new-embedding-secret")
        dialog._embedding_model_input.setText("new-embedding-model")
        dialog._embedding_dimensions_input.setValue(0)
        dialog._embedding_batch_size_input.setValue(32)
        dialog._embedding_timeout_input.setValue(90)
        dialog._save_agent_settings()

        llm_settings = llm_settings_service.load()
        embedding_settings = embedding_settings_service.load()
        assert llm_settings.providers[0].base_url == "https://chat.example.test"
        assert llm_settings.providers[0].api_key == "chat-secret"
        assert embedding_settings.provider_key == "semantic"
        assert embedding_settings.enabled is False
        assert embedding_settings.base_url == "https://new-embedding.example.test"
        assert embedding_settings.api_key == "new-embedding-secret"
        assert embedding_settings.model == "new-embedding-model"
        assert embedding_settings.dimensions is None
        assert embedding_settings.batch_size == 32
        assert embedding_settings.timeout_seconds == 90
        assert agent_saved == [True]
        assert embedding_saved == [True]
    finally:
        dialog.close()


@pytest.mark.parametrize("invalid_form", ["llm", "embedding"])
def test_settings_dialog_validates_both_forms_before_writing_either_file(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
    invalid_form: str,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / invalid_form / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    llm_settings_service = LLMSettingsService(paths)
    llm_settings_service.save(
        LLMSettings(
            providers=[
                LLMProviderConfig(
                    key="chat",
                    display_name="Chat",
                    base_url="https://chat.example.test",
                    api_key="original-chat-secret",
                    models=["chat-model"],
                )
            ],
            default_fq_model_key="chat/chat-model",
        )
    )
    embedding_settings_service = EmbeddingSettingsService(paths)
    embedding_settings_service.save(
        EmbeddingSettings(
            enabled=True,
            base_url="https://embedding.example.test",
            api_key="original-embedding-secret",
            model="embedding-model",
        )
    )
    original_llm_bytes = llm_settings_service.settings_path.read_bytes()
    original_embedding_bytes = embedding_settings_service.settings_path.read_bytes()
    translation_manager = TranslationManager(app, paths)
    translation_manager.set_locale("en_US", persist=False)
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translation_manager,
        LLMService(llm_settings_service),
        llm_settings_service,
        MLWorkerSettingsService(paths),
        embedding_settings_service=embedding_settings_service,
    )
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, text: warnings.append(str(text)),
    )
    dialog._provider_api_key_input.setText("changed-chat-secret")
    dialog._embedding_api_key_input.setText("changed-embedding-secret")
    if invalid_form == "llm":
        dialog._provider_models_input.clear()
    else:
        dialog._embedding_model_input.clear()

    try:
        dialog._save_agent_settings()

        assert warnings
        assert llm_settings_service.settings_path.read_bytes() == original_llm_bytes
        assert embedding_settings_service.settings_path.read_bytes() == original_embedding_bytes
    finally:
        dialog.close()


def _combo_values(selector) -> list[str]:
    return [str(selector.itemData(index)) for index in range(selector.count())]
