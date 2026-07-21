from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from xenix.ui.knowledge_workspace import (
    KnowledgeWorkspaceDialog,
    _accepted_import_paths,
)


class _ImportService:
    def list_imports(self):
        return [
            SimpleNamespace(
                file_name="rules.pdf",
                status="succeeded",
                reused_existing=False,
                error_summary=None,
            )
        ]


class _OcrDeployment:
    def status(self):
        return SimpleNamespace(installed=False, models_ready=False)


def test_import_path_filter_is_exact_case_insensitive_and_stably_deduplicated(tmp_path: Path) -> None:
    values = [
        str(tmp_path / "a.TXT"),
        str(tmp_path / "b.docx"),
        str(tmp_path / "c.doc"),
        str(tmp_path / "d.PPT"),
        str(tmp_path / "e.pptx"),
        str(tmp_path / "f.pdf"),
        str(tmp_path / "ignored.png"),
        str(tmp_path / "a.TXT"),
    ]

    accepted = _accepted_import_paths(values)

    assert [path.suffix.casefold() for path in accepted] == [
        ".txt",
        ".docx",
        ".doc",
        ".ppt",
        ".pptx",
        ".pdf",
    ]


def test_workspace_and_import_queue_are_modeless_singletons(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    workspace = KnowledgeWorkspaceDialog(
        import_service=_ImportService(),
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
    workspace.close()
