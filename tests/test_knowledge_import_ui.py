import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QEvent, QTranslator, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from xenix.services.paddle_ocr_service import PaddleOcrStatus
from xenix.services.knowledge_task_logs import KnowledgeTaskLogEntry
from xenix.services.knowledge_index_service import KnowledgeIndexKind
from xenix.ui import knowledge_workspace
from xenix.ui.knowledge_workspace import (
    KnowledgeWorkspaceDialog,
    _accepted_import_paths,
)


class _ImportService:
    def __init__(self, items: list | None = None) -> None:
        self.items = items or [
            SimpleNamespace(
                import_id="import-1",
                file_name="rules.pdf",
                status="canonical_ready",
                phase="derivation_queued",
                reused_existing=False,
                error_code=None,
                error_summary=None,
                retryable=False,
            )
        ]
        self.enqueued: list[Path] = []
        self.enqueue_thread_ids: list[int] = []
        self.list_calls = 0
        self.retries: list[tuple[str, str | None]] = []
        self.cancellations: list[str] = []
        self.logs = (
            KnowledgeTaskLogEntry(
                timestamp="2026-07-22T10:00:00+00:00",
                level="info",
                phase="parsing",
                event_code="parsing_started",
            ),
        )

    def enqueue_file(self, path: Path):
        self.enqueued.append(path)
        self.enqueue_thread_ids.append(threading.get_ident())
        return SimpleNamespace(status="queued", reused_existing=False)

    def list_imports(self):
        self.list_calls += 1
        return list(self.items)

    def retry_import(
        self,
        import_id: str,
        *,
        password: str | None = None,
        source_path: Path | None = None,
    ):
        del source_path
        self.retries.append((import_id, password))

    def cancel_import(self, import_id: str):
        self.cancellations.append(import_id)
        return True

    def read_import_logs(self, import_id: str):
        del import_id
        return self.logs


class _OcrDeployment:
    def __init__(self, status: PaddleOcrStatus | None = None) -> None:
        self.current_status = status or PaddleOcrStatus(False, False)
        self.status_thread_ids: list[int] = []
        self.install_thread_ids: list[int] = []

    def status(self):
        self.status_thread_ids.append(threading.get_ident())
        return self.current_status

    def install(self, progress):
        self.install_thread_ids.append(threading.get_ident())
        progress("downloading_python")
        progress("ready")
        self.current_status = PaddleOcrStatus(True, True)
        return self.current_status


class _KnowledgeService:
    def __init__(self) -> None:
        self.documents = [
            SimpleNamespace(
                title="Rainy season rules",
                source_format="pdf",
                content_state="ready",
                updated_at=datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
            )
        ]

    def list_documents(self):
        return list(self.documents)


class _UnavailableKnowledgeService:
    def list_documents(self):
        raise RuntimeError("database unavailable")


class _IndexService:
    def __init__(self) -> None:
        self.enqueued: list[tuple[tuple[str, ...], str]] = []

    def status(self):
        return SimpleNamespace(
            keyword_state="ready",
            text_vector_state="needs_rebuild",
            vector_configured=True,
            unit_count=4,
            estimated_vector_requests=1,
        )

    def enqueue_rebuild(self, kinds, *, trigger):
        self.enqueued.append((tuple(str(kind) for kind in kinds), trigger))
        return "index-task-1"


def _app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _drain_workspace_tasks(workspace: KnowledgeWorkspaceDialog, app: QApplication) -> None:
    assert workspace._thread_pool.waitForDone(2_000)
    app.processEvents()


def test_import_path_filter_is_exact_case_insensitive_and_stably_deduplicated(tmp_path: Path) -> None:
    values = [
        str(tmp_path / "a.TXT"),
        str(tmp_path / "b.docx"),
        str(tmp_path / "c.doc"),
        str(tmp_path / "ignored.PPT"),
        str(tmp_path / "also-ignored.pptx"),
        str(tmp_path / "d.pdf"),
        str(tmp_path / "e.JPG"),
        str(tmp_path / "f.JPEG"),
        str(tmp_path / "g.png"),
        str(tmp_path / "a.TXT"),
    ]

    accepted = _accepted_import_paths(values)

    assert [path.suffix.casefold() for path in accepted] == [
        ".txt",
        ".docx",
        ".doc",
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
    ]


def test_workspace_and_import_queue_are_modeless_singletons_with_owned_polling_timer(
    monkeypatch,
) -> None:
    app = _app(monkeypatch)
    monkeypatch.setattr(knowledge_workspace, "IMPORT_POLL_INTERVAL_MS", 10)
    imports = _ImportService()
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        ocr_deployment=_OcrDeployment(),
    )

    workspace.open_import_queue()
    first = workspace._queue_dialog
    workspace.open_import_queue()
    second = workspace._queue_dialog
    app.processEvents()

    assert workspace.windowModality() == Qt.NonModal
    assert first is second
    assert first is not None and first.windowModality() == Qt.NonModal
    assert first._list.count() == 1
    assert first._refresh_timer.isActive()

    first.hide()
    app.processEvents()
    assert not first._refresh_timer.isActive()
    first.show()
    app.processEvents()
    assert first._refresh_timer.isActive()
    first.close()
    app.processEvents()
    assert not first._refresh_timer.isActive()
    workspace.close()


def test_workspace_degrades_to_a_bounded_unavailable_state_when_listing_fails(
    monkeypatch,
) -> None:
    app = _app(monkeypatch)
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        knowledge_service=_UnavailableKnowledgeService(),
    )

    workspace.refresh_documents()
    app.processEvents()

    assert workspace._documents.rowCount() == 0
    assert workspace._documents.isHidden()
    assert workspace._empty_state.text() == (
        "Knowledge content is temporarily unavailable."
    )
    workspace.close()


def test_queue_translates_status_phase_error_and_reused_without_raw_summary(monkeypatch) -> None:
    app = _app(monkeypatch)
    raw_summary = r"Failed at F:\private\rules.pdf with api-token-secret"
    imports = _ImportService(
        [
            SimpleNamespace(
                import_id="import-secret",
                file_name="rules.pdf",
                status="needs_attention",
                phase="needs_attention",
                reused_existing=True,
                error_code="knowledge_password_required",
                error_summary=raw_summary,
                retryable=True,
            )
        ]
    )
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        ocr_deployment=_OcrDeployment(),
    )

    workspace.open_import_queue()
    app.processEvents()
    text = workspace._queue_dialog._list.item(0).text()

    assert "Status: Needs attention" in text
    assert "Phase: Needs attention" in text
    assert "Reused existing document" in text
    assert "A password is required to continue this import." in text
    assert raw_summary not in text
    assert "knowledge_password_required" not in text
    workspace.close()


def test_queue_password_retry_is_transient_and_cancel_uses_import_identity(monkeypatch) -> None:
    app = _app(monkeypatch)
    imports = _ImportService(
        [
            SimpleNamespace(
                import_id="import-secret",
                file_name="encrypted.pdf",
                status="needs_attention",
                phase="needs_attention",
                reused_existing=False,
                error_code="knowledge_password_required",
                error_summary=None,
                retryable=True,
            )
        ]
    )
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        ocr_deployment=_OcrDeployment(),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *_args, **_kwargs: ("transient-pass", True),
    )
    workspace.open_import_queue()
    queue_dialog = workspace._queue_dialog
    assert queue_dialog is not None
    queue_dialog._list.setCurrentRow(0)

    queue_dialog._retry_selected()

    assert imports.retries == [("import-secret", "transient-pass")]

    imports.items = [
        SimpleNamespace(
            import_id="import-running",
            file_name="rules.pdf",
            status="running",
            phase="parsing",
            reused_existing=False,
            error_code=None,
            error_summary=None,
            retryable=False,
        )
    ]
    queue_dialog.refresh()
    queue_dialog._list.setCurrentRow(0)
    queue_dialog._cancel_selected()

    assert imports.cancellations == ["import-running"]
    workspace.close()


def test_queue_opens_a_modeless_bounded_import_log_view(monkeypatch) -> None:
    app = _app(monkeypatch)
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        ocr_deployment=_OcrDeployment(),
    )
    workspace.open_import_queue()
    queue_dialog = workspace._queue_dialog
    assert queue_dialog is not None
    queue_dialog._list.setCurrentRow(0)

    queue_dialog._view_selected_log()
    app.processEvents()

    log_dialog = queue_dialog._log_dialog
    assert log_dialog is not None
    assert log_dialog.windowModality() == Qt.NonModal
    assert "Document parsing" in log_dialog._content.toPlainText()
    assert "Document parsing started" in log_dialog._content.toPlainText()
    assert log_dialog._refresh_timer.isActive()

    queue_dialog.hide()
    app.processEvents()
    assert not log_dialog._refresh_timer.isActive()
    workspace.close()


def test_file_selection_enqueues_on_gui_thread_and_uses_exact_format_filter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = _app(monkeypatch)
    imports = _ImportService([])
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        ocr_deployment=_OcrDeployment(),
    )
    selected = [
        str(tmp_path / "rules.txt"),
        str(tmp_path / "scan.jpeg"),
        str(tmp_path / "slides.pptx"),
    ]
    captured: dict[str, str] = {}

    def choose_files(*args, **_kwargs):
        captured["filter"] = str(args[3])
        return selected, ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", choose_files)

    workspace._choose_files()
    app.processEvents()

    assert [path.suffix for path in imports.enqueued] == [".txt", ".jpeg"]
    assert captured["filter"] == (
        "Knowledge documents (*.txt *.doc *.docx *.pdf *.jpg *.jpeg *.png)"
    )
    assert imports.enqueue_thread_ids == [threading.get_ident(), threading.get_ident()]
    assert workspace._queue_dialog is not None
    assert workspace._queue_dialog._refresh_timer.isActive()
    workspace.close()


def test_queue_translates_snapshot_and_bounded_format_failures(monkeypatch) -> None:
    app = _app(monkeypatch)
    imports = _ImportService(
        [
            SimpleNamespace(
                import_id="import-bounded",
                file_name="unsafe.docx",
                status="failed",
                phase="snapshot",
                reused_existing=False,
                error_code="knowledge_docx_compression_ratio",
                error_summary=r"F:\private\unsafe.docx",
                retryable=False,
            )
        ]
    )
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        ocr_deployment=_OcrDeployment(),
    )

    workspace.open_import_queue()
    app.processEvents()
    text = workspace._queue_dialog._list.item(0).text()

    assert "Phase: Copying source" in text
    assert "The DOCX package compression ratio is unsafe." in text
    assert "private" not in text
    workspace.close()


def test_ocr_status_probe_runs_off_gui_thread_and_language_change_uses_cache(monkeypatch) -> None:
    app = _app(monkeypatch)
    deployment = _OcrDeployment(PaddleOcrStatus(True, True))
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        ocr_deployment=deployment,
    )

    workspace.show()
    _drain_workspace_tasks(workspace, app)

    assert deployment.status_thread_ids
    assert all(thread_id != threading.get_ident() for thread_id in deployment.status_thread_ids)
    assert workspace._ocr_status.text() == "Local PaddleOCR is ready"
    probe_count = len(deployment.status_thread_ids)

    workspace.changeEvent(QEvent(QEvent.LanguageChange))

    assert len(deployment.status_thread_ids) == probe_count
    assert workspace._ocr_status.text() == "Local PaddleOCR is ready"
    workspace.close()


def test_hidden_workspace_ignores_late_probe_and_reopen_starts_a_fresh_probe(monkeypatch) -> None:
    app = _app(monkeypatch)
    started = threading.Event()
    release = threading.Event()

    class BlockingDeployment(_OcrDeployment):
        def status(self):
            self.status_thread_ids.append(threading.get_ident())
            if len(self.status_thread_ids) == 1:
                started.set()
                assert release.wait(2)
            return PaddleOcrStatus(True, True)

    deployment = BlockingDeployment()
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        ocr_deployment=deployment,
    )
    workspace.show()
    assert started.wait(2)
    initial_text = workspace._ocr_status.text()

    workspace.hide()
    release.set()
    _drain_workspace_tasks(workspace, app)

    assert workspace._ocr_status.text() == initial_text

    workspace.show()
    _drain_workspace_tasks(workspace, app)

    assert len(deployment.status_thread_ids) == 2
    assert workspace._ocr_status.text() == "Local PaddleOCR is ready"
    workspace.close()


def test_workspace_lists_logical_documents_and_opens_knowledge_settings(monkeypatch) -> None:
    app = _app(monkeypatch)
    opened: list[bool] = []
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        knowledge_service=_KnowledgeService(),
        ocr_deployment=_OcrDeployment(),
        open_knowledge_settings=lambda: opened.append(True),
    )
    workspace.show()
    _drain_workspace_tasks(workspace, app)

    assert workspace._documents.rowCount() == 1
    assert workspace._documents.item(0, 0).text() == "Rainy season rules"
    assert workspace._documents.item(0, 1).text() == "PDF"
    assert workspace._documents.item(0, 2).text() == "Searchable"
    assert workspace._documents.item(0, 0).data(Qt.UserRole) is None

    workspace._settings_button.click()
    assert opened == [True]
    workspace.close()


def test_workspace_manual_rebuild_sheet_lists_only_real_indexes(monkeypatch) -> None:
    app = _app(monkeypatch)
    indexes = _IndexService()
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        knowledge_service=_KnowledgeService(),
        knowledge_index_service=indexes,
        ocr_deployment=_OcrDeployment(),
    )

    workspace._open_index_rebuild()
    app.processEvents()
    sheet = workspace._index_dialog
    assert sheet is not None
    assert sheet.windowModality() == Qt.WindowModal
    assert sheet._keyword_checkbox.text() == "Keyword index"
    assert sheet._text_vector_checkbox.text() == "Text semantic vector index"
    assert "Visual" not in " ".join(
        child.text() for child in sheet.findChildren(type(sheet._keyword_checkbox))
    )

    sheet._text_vector_checkbox.setChecked(False)
    sheet._submit()

    assert indexes.enqueued == [
        ((KnowledgeIndexKind.KEYWORD.value,), "manual")
    ]
    workspace.close()


def test_manual_rebuild_sheet_keeps_translated_standard_button_after_language_change(
    monkeypatch,
) -> None:
    app = _app(monkeypatch)
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        knowledge_service=_KnowledgeService(),
        knowledge_index_service=_IndexService(),
        ocr_deployment=_OcrDeployment(),
    )
    workspace._open_index_rebuild()
    sheet = workspace._index_dialog
    assert sheet is not None
    translator = QTranslator(app)
    catalog = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "xenix"
        / "translations"
        / "xenix_zh_CN.qm"
    )
    assert translator.load(str(catalog))

    try:
        app.installTranslator(translator)
        app.processEvents()

        assert sheet._rebuild_button.text() == "重建"
        assert sheet._cancel_button.text() == "取消"
    finally:
        app.removeTranslator(translator)
        workspace.close()


def test_knowledge_workspace_translation_catalog_entries_are_complete() -> None:
    translations = Path(__file__).resolve().parents[1] / "src" / "xenix" / "translations"

    for catalog_name in ("xenix_en_US.ts", "xenix_zh_CN.ts"):
        root = ET.parse(translations / catalog_name).getroot()
        contexts = {
            context.findtext("name"): context
            for context in root.findall("context")
        }
        for context_name in (
            "KnowledgeImportLogDialog",
            "KnowledgeImportQueueDialog",
            "KnowledgeIndexRebuildDialog",
            "KnowledgeWorkspaceDialog",
        ):
            messages = contexts[context_name].findall("message")
            active = [message for message in messages if message.find("location") is not None]
            unfinished = [
                message.findtext("source")
                for message in active
                if message.find("translation") is None
                or message.find("translation").get("type") == "unfinished"
                or not (message.findtext("translation") or "").strip()
            ]
            assert unfinished == []
