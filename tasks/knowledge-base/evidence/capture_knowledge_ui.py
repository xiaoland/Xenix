"""Capture the Slice 02 Knowledge UI surfaces for offscreen visual review."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "build" / "knowledge-ui-qa"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XENIX_APP_HOME"] = str(OUTPUT_ROOT / "runtime")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QScrollArea

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.i18n import TranslationManager
from xenix.services.embedding_service import EmbeddingSettings, EmbeddingSettingsService
from xenix.services.llm import LLMService, LLMSettingsService
from xenix.services.ml.worker_settings import MLWorkerSettingsService
from xenix.services.paddle_ocr_service import PaddleOcrStatus
from xenix.ui.knowledge_workspace import KnowledgeWorkspaceDialog
from xenix.ui.settings_dialog import SettingsDialog, SettingsTab


class _Imports:
    def list_imports(self):
        return [
            SimpleNamespace(
                import_id="ready",
                file_name="market-notes.docx",
                status="canonical_ready",
                phase="completed",
                reused_existing=False,
                error_code=None,
                retryable=False,
            ),
            SimpleNamespace(
                import_id="running",
                file_name="field-scan.pdf",
                status="running",
                phase="parsing",
                reused_existing=False,
                error_code=None,
                retryable=False,
            ),
            SimpleNamespace(
                import_id="password",
                file_name="private-handbook.pdf",
                status="needs_attention",
                phase="needs_attention",
                reused_existing=False,
                error_code="knowledge_password_required",
                retryable=True,
            ),
        ]

    def enqueue_file(self, _path):
        return None

    def retry_import(self, *_args, **_kwargs):
        return None

    def cancel_import(self, _import_id):
        return True

    def read_import_logs(self, _import_id):
        return (
            SimpleNamespace(
                timestamp="2026-07-22T08:00:00+00:00",
                phase="queued",
                event_code="import_queued",
            ),
            SimpleNamespace(
                timestamp="2026-07-22T08:00:01+00:00",
                phase="parsing",
                event_code="worker_started",
            ),
            SimpleNamespace(
                timestamp="2026-07-22T08:00:03+00:00",
                phase="completed",
                event_code="import_completed",
            ),
        )


class _Derivations:
    def status_for_import(self, import_id: str):
        if import_id == "ready":
            return SimpleNamespace(
                status="succeeded",
                phase="completed",
                error_code=None,
                retryable=False,
            )
        if import_id == "running":
            return SimpleNamespace(
                status="queued",
                phase="queued",
                error_code=None,
                retryable=False,
            )
        return None

    def retry_for_import(self, _import_id):
        return None


class _Ocr:
    def status(self) -> PaddleOcrStatus:
        return PaddleOcrStatus(True, True)

    def install(self, _progress) -> PaddleOcrStatus:
        return self.status()


class _Knowledge:
    def list_documents(self):
        updated = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)
        return [
            SimpleNamespace(
                title="Rainy-season restock rules",
                source_format="docx",
                content_state="ready",
                updated_at=updated,
            ),
            SimpleNamespace(
                title="Regional store visit notes",
                source_format="txt",
                content_state="processing",
                updated_at=updated,
            ),
            SimpleNamespace(
                title="Product display reference",
                source_format="png",
                content_state="no_searchable_text",
                updated_at=updated,
            ),
        ]


class _Indexes:
    def status(self):
        return SimpleNamespace(
            keyword_state="ready",
            text_vector_state="needs_rebuild",
            vector_configured=True,
            unit_count=37,
            estimated_vector_requests=1,
            active_task_id=None,
            active_task_status=None,
            error_code=None,
        )

    def enqueue_rebuild(self, _kinds, *, trigger):
        assert trigger == "manual"
        return "visual-task"

    def embedding_change_requires_confirmation(self, _previous, _proposed):
        return False


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True)
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")
    font_families = QFontDatabase.applicationFontFamilies(font_id)
    if not font_families:
        raise RuntimeError("Visual QA font could not be loaded.")
    app.setFont(QFont(font_families[0], 9))
    paths = ensure_app_dirs(get_app_paths())
    translations = TranslationManager(app, paths)
    translations.set_locale("en_US", persist=False)

    workspace = KnowledgeWorkspaceDialog(
        import_service=_Imports(),
        derivation_service=_Derivations(),
        knowledge_service=_Knowledge(),
        knowledge_index_service=_Indexes(),
        ocr_deployment=_Ocr(),
        open_knowledge_settings=lambda: None,
    )
    workspace._cached_ocr_status = PaddleOcrStatus(True, True)
    workspace.show()
    workspace.open_import_queue()
    app.processEvents()
    _capture(workspace, "workspace-en.png")
    assert workspace._queue_dialog is not None
    _capture(workspace._queue_dialog, "queue-en.png")
    workspace._queue_dialog._list.setCurrentRow(0)
    workspace._queue_dialog._view_selected_log()
    assert workspace._queue_dialog._log_dialog is not None
    _capture(workspace._queue_dialog._log_dialog, "import-log-en.png")
    workspace._open_index_rebuild()
    assert workspace._index_dialog is not None
    app.processEvents()
    _capture(workspace._index_dialog, "rebuild-index-en.png")
    workspace._index_dialog.hide()
    app.processEvents()

    embedding_settings = EmbeddingSettingsService(paths)
    embedding_settings.save(
        EmbeddingSettings(
            enabled=True,
            provider_key="openai-compatible",
            base_url="https://api.example.com/v1",
            api_key="visual-placeholder",
            model="text-embedding-model",
            dimensions=1536,
            batch_size=64,
            timeout_seconds=120,
        )
    )
    llm_settings = LLMSettingsService(paths)
    settings = SettingsDialog(
        paths,
        paths.logs / "xenix.log",
        paths.state / "xenix.db",
        translations,
        LLMService(llm_settings),
        llm_settings,
        MLWorkerSettingsService(paths),
        embedding_settings,
        paddle_ocr_deployment=_Ocr(),
        knowledge_index_service=_Indexes(),
    )
    settings.show_tab(SettingsTab.KNOWLEDGE_BASE)
    settings.show()
    settings._cached_ocr_status = PaddleOcrStatus(True, True)
    settings._render_ocr_status()
    app.processEvents()
    scroll = settings.findChild(QScrollArea)
    assert scroll is not None
    scroll.ensureWidgetVisible(settings._embedding_card, 0, 24)
    app.processEvents()
    _capture(settings, "settings-knowledge-en.png")

    translations.set_locale("zh_CN", persist=False)
    app.processEvents()
    _capture(workspace, "workspace-zh.png")
    _capture(workspace._queue_dialog, "queue-zh.png")
    _capture(workspace._queue_dialog._log_dialog, "import-log-zh.png")
    _capture(settings, "settings-knowledge-zh.png")
    workspace._index_dialog.open()
    app.processEvents()
    _capture(workspace._index_dialog, "rebuild-index-zh.png")

    settings.close()
    workspace.close()
    app.processEvents()
    print(OUTPUT_ROOT)
    return 0


def _capture(widget, name: str) -> None:
    image = widget.grab()
    if image.isNull() or not image.save(str(OUTPUT_ROOT / name)):
        raise RuntimeError(f"Could not capture {name}.")


if __name__ == "__main__":
    raise SystemExit(main())
