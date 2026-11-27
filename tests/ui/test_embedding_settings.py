from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton
from pytestqt.qtbot import QtBot

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import TranslationManager
from xenix.services.ai_settings import AIConversationSettingsSource, AIEmbeddingSettingsSource, AISettingsService
from xenix.services.embedding_service import (
    EmbeddingSettings,
    EmbeddingSettingsService,
    embedding_profile_from_settings,
)
from xenix.services.knowledge_index_service import KnowledgeIndexService
from xenix.services.llm import LLMProviderConfig, LLMService, LLMSettings, LLMSettingsService
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.ui.settings import SettingsDialog, SettingsTab
from tests.support.ui_queries import find_control


def test_embedding_model_change_requires_user_confirmation_before_rebuild(
    monkeypatch,
    tmp_path: Path,
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    class Indexes:
        embedding_change_requires_confirmation = KnowledgeIndexService.embedding_change_requires_confirmation

        def __init__(self) -> None:
            self.enqueued: list[tuple[tuple[str, ...], str]] = []

        def has_searchable_content(self, *, library_id):
            return library_id == "global"

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
    chat_provider = LLMProviderConfig(
        key="openai",
        base_url="https://chat.example.test",
        api_key="fake-chat-key",
        models=["chat", "title"],
        embedding_models=["namespace/meaning-v2"],
    )
    LLMSettingsService(paths).save(LLMSettings(
        providers=[chat_provider],
        default_fq_model_key="openai/chat",
        thread_title_fq_model_key="openai/title",
    ))
    embedding = EmbeddingSettings(
        enabled=True,
        base_url="https://embedding.example.test",
        api_key="fake-embedding-key",
        model="meaning-v1",
        dimensions=64,
        batch_size=10,
        timeout_seconds=60,
    )
    legacy_embeddings = EmbeddingSettingsService(paths)
    legacy_embeddings.save(embedding)
    settings = AISettingsService(paths)
    llm = LLMService(AIConversationSettingsSource(settings))
    embeddings = AIEmbeddingSettingsSource(settings)

    assert embeddings.load() == embedding
    before = embedding_profile_from_settings(embedding).profile_fingerprint
    assert embedding_profile_from_settings(embeddings.load()).profile_fingerprint == before
    indexes = Indexes()
    dialog = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        TranslationManager(qapp, paths),
        settings,
        MLWorkerSettingsService(paths),
        knowledge_index_service=indexes,
    )
    qtbot.addWidget(dialog)

    title = find_control(dialog, "settings.llm.thread-title-model", QComboBox)
    model = find_control(dialog, "settings.embedding.model", QComboBox)
    provider_url = find_control(dialog, "settings.llm.provider.base-url", QLineEdit)
    save_button = find_control(dialog, "settings.save", QPushButton)

    try:
        dialog.show_tab(SettingsTab.CONVERSATION)
        assert title.currentData() == "openai/title"
        assert [title.itemData(i) for i in range(title.count())] == ["", "openai/chat", "openai/title"]
        dialog.show_tab(SettingsTab.KNOWLEDGE_BASE)
        assert model.currentData() == "embedding/meaning-v1"
        assert [model.itemData(i) for i in range(model.count())] == [
            "", "openai/namespace/meaning-v2", "embedding/meaning-v1",
        ]
        save_button.click()
        assert settings.settings_path.exists()
        assert embedding_profile_from_settings(embeddings.load()).profile_fingerprint == before
        assert indexes.enqueued == []

        monkeypatch.setattr(
            dialog,
            "_confirm_embedding_compatibility_change",
            lambda: "rebuild",
        )
        model.setCurrentIndex(model.findData("openai/namespace/meaning-v2"))
        save_button.click()

        assert embeddings.load().model == "namespace/meaning-v2"
        assert embeddings.load().api_key == chat_provider.api_key
        assert llm.thread_title_fq_model_key() == "openai/title"
        assert indexes.enqueued == [(("text_vector",), "settings_change")]

        monkeypatch.setattr(
            dialog,
            "_confirm_embedding_compatibility_change",
            lambda: "cancel",
        )
        dialog.show_tab(SettingsTab.AI)
        provider_url.setText("https://edited.example.test")
        save_button.click()

        assert embeddings.load().base_url == chat_provider.base_url
        assert legacy_embeddings.load() == embedding
        assert indexes.enqueued == [(("text_vector",), "settings_change")]
    finally:
        dialog.close()
