from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog

from xenix.services.knowledge_index_service import KnowledgeIndexOverview
from xenix.services.knowledge_service import KnowledgeDocumentSummary
from xenix.services.knowledge_task_query import KnowledgeTaskItem, KnowledgeTaskSummary
from xenix.services.knowledge_workspace_service import KnowledgeWorkspaceSnapshot
from xenix.services.paddle_ocr_service import PaddleOcrState, PaddleOcrStatus
from xenix.ui.knowledge_workspace import KnowledgeWorkspaceDialog, _accepted_import_paths


def _app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    QCoreApplication.processEvents()
    return app


class _ImportService:
    def __init__(self) -> None:
        self.enqueued: list[Path] = []
        self.cancelled: list[str] = []
        self.retried: list[tuple[str, str | None, Path | None]] = []

    def enqueue_file(self, path: Path):
        self.enqueued.append(path)

    def cancel_import(self, import_id: str):
        self.cancelled.append(import_id)

    def retry_import(self, import_id: str, *, password=None, source_path=None):
        self.retried.append((import_id, password, source_path))

    def read_import_logs(self, _import_id: str):
        return ()


class _TaskQuery:
    def __init__(self, tasks: list[KnowledgeTaskItem] | None = None) -> None:
        self.tasks = list(tasks or ())

    def list_tasks(self):
        return list(self.tasks)


class _SnapshotService:
    def __init__(self, snapshot: KnowledgeWorkspaceSnapshot, *, block=None) -> None:
        self.value = snapshot
        self.block = block
        self.calls: list[int] = []

    def snapshot(self):
        self.calls.append(threading.get_ident())
        if self.block is not None:
            self.block()
        return self.value


def _snapshot(*, active: int = 0) -> KnowledgeWorkspaceSnapshot:
    now = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    return KnowledgeWorkspaceSnapshot(
        documents=(
            KnowledgeDocumentSummary(
                title="运营规则",
                source_format="pdf",
                content_state="ready",
                imported_at=now,
                updated_at=now,
            ),
        ),
        tasks=KnowledgeTaskSummary(active, 0, active),
        ocr=PaddleOcrStatus(PaddleOcrState.READY),
        indexes=KnowledgeIndexOverview(
            keyword_state="ready",
            text_vector_state="needs_rebuild",
            vector_configured=True,
            unit_count=3,
            estimated_vector_requests=1,
            active_task_id="task" if active else None,
            active_task_status="running" if active else None,
            error_code=None,
        ),
    )


def _drain(workspace: KnowledgeWorkspaceDialog, app: QApplication) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        app.processEvents()
        if workspace._snapshot_task is None and workspace._last_snapshot is not None:
            break
        time.sleep(0.005)
    app.processEvents()


def _drain_queue(queue, app: QApplication) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        app.processEvents()
        if queue._load_task is None and queue._table.rowCount() > 0:
            break
        time.sleep(0.005)
    app.processEvents()


def test_supported_file_admission_is_exact_and_deduplicated(tmp_path: Path) -> None:
    txt = tmp_path / "rules.txt"
    jpeg = tmp_path / "scan.JPEG"
    accepted = _accepted_import_paths(
        [str(txt), str(txt), str(jpeg), str(tmp_path / "slides.pptx")]
    )
    assert accepted == [
        txt.resolve(),
        jpeg.resolve(),
        (tmp_path / "slides.pptx").resolve(),
    ]


def test_workspace_shows_shell_before_background_snapshot_and_has_no_description(
    monkeypatch,
) -> None:
    app = _app(monkeypatch)
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        assert release.wait(2)

    service = _SnapshotService(_snapshot(), block=block)
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        task_query_service=_TaskQuery(),
        workspace_service=service,
    )
    before = time.perf_counter()
    workspace.show()
    app.processEvents()

    assert time.perf_counter() - before < 0.5
    assert workspace.isVisible()
    assert not hasattr(workspace, "_description")
    assert started.wait(2)
    assert service.calls[0] != threading.get_ident()
    release.set()
    _drain(workspace, app)
    workspace.close()


def test_workspace_lists_documents_and_places_quiet_status_in_footer(monkeypatch) -> None:
    app = _app(monkeypatch)
    service = _SnapshotService(_snapshot())
    opened: list[bool] = []
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        task_query_service=_TaskQuery(),
        workspace_service=service,
        open_knowledge_settings=lambda: opened.append(True),
    )
    workspace.show()
    _drain(workspace, app)

    assert workspace._documents.rowCount() == 1
    assert workspace._documents.item(0, 0).text() == "运营规则"
    assert workspace._documents.item(0, 1).text() == "PDF"
    assert "OCR: Ready" in workspace._footer_status.text()
    assert "Keyword: Ready" in workspace._footer_status.text()
    assert "Text vectors: Needs rebuild" in workspace._footer_status.text()
    assert workspace._footer_status.font().pointSize() < workspace.font().pointSize()
    assert not workspace._refresh_timer.isActive()
    workspace._settings_button.click()
    assert opened == [True]
    workspace.close()


def test_workspace_polls_only_while_snapshot_reports_active_work(monkeypatch) -> None:
    app = _app(monkeypatch)
    service = _SnapshotService(_snapshot(active=1))
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        task_query_service=_TaskQuery(),
        workspace_service=service,
    )
    workspace.show()
    _drain(workspace, app)
    assert workspace._refresh_timer.isActive()

    service.value = _snapshot(active=0)
    workspace.refresh_documents()
    _drain(workspace, app)
    assert not workspace._refresh_timer.isActive()
    workspace.close()


def test_hidden_workspace_ignores_late_snapshot_and_reopen_uses_new_generation(
    monkeypatch,
) -> None:
    app = _app(monkeypatch)
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        assert release.wait(2)

    service = _SnapshotService(_snapshot(), block=block)
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        task_query_service=_TaskQuery(),
        workspace_service=service,
    )
    workspace.show()
    app.processEvents()
    assert started.wait(2)
    workspace.hide()
    release.set()
    _drain(workspace, app)
    assert workspace._documents.rowCount() == 0

    service.block = None
    workspace.show()
    _drain(workspace, app)
    assert workspace._documents.rowCount() == 1
    workspace.close()


def test_knowledge_task_queue_unifies_task_kinds_and_capability_actions(monkeypatch) -> None:
    app = _app(monkeypatch)
    now = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    tasks = [
        KnowledgeTaskItem(
            reference="import:1",
            kind="import",
            target="rules.pdf",
            status="running",
            phase="parsing",
            trigger="user",
            updated_at=now,
            error_code=None,
            owner="import",
            owner_id="1",
            import_id="1",
            can_cancel=True,
            can_view_log=True,
        ),
        KnowledgeTaskItem(
            reference="derivation:2",
            kind="content_preparation",
            target="运营规则",
            status="failed",
            phase="failed",
            trigger="compatibility",
            updated_at=now,
            error_code="knowledge_derivation_failed",
            owner="derivation",
            owner_id="2",
            import_id="1",
            can_retry=True,
        ),
        KnowledgeTaskItem(
            reference="index:3",
            kind="index_build",
            target="Text vector index",
            status="queued",
            phase="queued",
            trigger="manual",
            updated_at=now,
            error_code=None,
            owner="index",
            owner_id="3",
            import_id=None,
            index_kinds=("text_vector",),
        ),
    ]
    imports = _ImportService()
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        task_query_service=_TaskQuery(tasks),
        workspace_service=_SnapshotService(_snapshot()),
    )
    workspace.open_task_queue()
    queue = workspace._queue_dialog
    assert queue is not None
    _drain_queue(queue, app)

    assert queue.windowModality() == Qt.NonModal
    assert queue._table.rowCount() == 3
    assert [queue._table.item(row, 0).text() for row in range(3)] == [
        "Import",
        "Content preparation",
        "Index build",
    ]
    assert "import:1" not in " ".join(
        queue._table.item(row, column).text()
        for row in range(3)
        for column in range(4)
    )
    queue._table.selectRow(0)
    queue._sync_actions()
    assert queue._cancel_button.isEnabled()
    assert queue._view_log_button.isEnabled()
    assert not queue._retry_button.isEnabled()
    queue._cancel_button.click()
    assert imports.cancelled == ["1"]
    queue.close()


def test_visible_idle_task_queue_refreshes_when_reopened(monkeypatch) -> None:
    app = _app(monkeypatch)
    query = _TaskQuery()
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
        task_query_service=query,
        workspace_service=_SnapshotService(_snapshot()),
    )
    workspace.open_task_queue()
    queue = workspace._queue_dialog
    assert queue is not None
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and queue._load_task is not None:
        app.processEvents()
        time.sleep(0.005)
    assert queue._table.rowCount() == 0
    assert queue._refresh_timer.isActive()

    query.tasks = [
        KnowledgeTaskItem(
            reference="index:1",
            kind="index_build",
            target="Keyword index",
            status="queued",
            phase="queued",
            trigger="manual",
            updated_at=datetime(2026, 7, 22, 8, 0, tzinfo=UTC),
            error_code=None,
            owner="index",
            owner_id="1",
            import_id=None,
            index_kinds=("keyword",),
        )
    ]
    workspace.open_task_queue()
    _drain_queue(queue, app)

    assert queue._table.rowCount() == 1
    queue.close()


def test_file_selection_uses_lightweight_format_registry_and_opens_task_queue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = _app(monkeypatch)
    imports = _ImportService()
    captured: dict[str, str] = {}

    def choose_files(*args, **_kwargs):
        captured["filter"] = str(args[3])
        return [str(tmp_path / "rules.txt"), str(tmp_path / "slides.pptx")], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", choose_files)
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        task_query_service=_TaskQuery(),
        workspace_service=_SnapshotService(_snapshot()),
    )

    workspace._choose_files()
    app.processEvents()

    assert [path.suffix for path in imports.enqueued] == [".txt", ".pptx"]
    assert captured["filter"] == (
        "Knowledge documents (*.txt *.doc *.docx *.ppt *.pptx *.pdf *.jpg *.jpeg *.png)"
    )
    assert workspace._queue_dialog is not None
    workspace.close()


def test_workspace_drop_uses_the_same_ordered_deduplicated_submission(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = _app(monkeypatch)
    imports = _ImportService()
    workspace = KnowledgeWorkspaceDialog(
        import_service=imports,
        task_query_service=_TaskQuery(),
        workspace_service=_SnapshotService(_snapshot()),
    )
    txt = tmp_path / "rules.txt"
    pptx = tmp_path / "slides.pptx"
    unsupported = tmp_path / "notes.md"
    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(txt)),
            QUrl.fromLocalFile(str(pptx)),
            QUrl.fromLocalFile(str(txt)),
            QUrl.fromLocalFile(str(unsupported)),
        ]
    )
    target = workspace._documents.viewport()
    drag = QDragEnterEvent(
        QPoint(4, 4),
        Qt.CopyAction,
        mime_data,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(target, drag)

    assert drag.isAccepted()

    drop = QDropEvent(
        QPointF(4, 4),
        Qt.CopyAction,
        mime_data,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(target, drop)
    app.processEvents()

    assert imports.enqueued == [txt.resolve(), pptx.resolve()]
    assert workspace._queue_dialog is not None
    workspace.close()
