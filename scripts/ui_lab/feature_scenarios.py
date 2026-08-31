"""Synthetic ports for the same feature widgets used by production composition."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from xenix.services.llm import LLMProviderConfig, LLMSettings
from xenix.services.paddle_ocr_service import PaddleOcrState, PaddleOcrStatus
from xenix.ui.history import HistoryPanel, HistoryThreadSummary
from xenix.ui.settings.ocr import OcrSettingsCard
from xenix.ui.settings.provider import ProviderSettingsEditor

from .contracts import ScenarioContext, ScenarioHandle, ready_immediately


class _SyntheticHistory:
    def __init__(self) -> None:
        self._threads = [
            HistoryThreadSummary("thread:synthetic:001", "Quarterly sales overview"),
            HistoryThreadSummary("thread:synthetic:002", None),
            HistoryThreadSummary("thread:synthetic:003", "Regional demand forecast"),
        ]

    def list_threads(self) -> Sequence[HistoryThreadSummary]:
        return tuple(self._threads)

    def rename_thread(self, thread_id: str, title: str | None) -> HistoryThreadSummary:
        summary = HistoryThreadSummary(thread_id, title)
        self._threads = [summary if row.id == thread_id else row for row in self._threads]
        return summary

    def delete_thread(self, thread_id: str) -> None:
        self._threads = [row for row in self._threads if row.id != thread_id]

    def has_title_provider(self) -> bool:
        return True

    def generate_thread_title(self, thread_id: str) -> str:
        return "Synthetic thread title"


def build_history_populated(_context: ScenarioContext) -> ScenarioHandle:
    panel = HistoryPanel(_SyntheticHistory(), is_thread_running=lambda _thread_id: False)
    panel.refresh("thread:synthetic:001")
    return ScenarioHandle(panel, ready_immediately, panel.shutdown)


class _SyntheticOcr:
    def status_snapshot(self) -> PaddleOcrStatus:
        return PaddleOcrStatus(PaddleOcrState.READY)

    def status(self) -> PaddleOcrStatus:
        return self.status_snapshot()

    def verify_active(self) -> PaddleOcrStatus:
        return self.status_snapshot()

    def install(self, progress: Callable[[str], None] | None = None) -> PaddleOcrStatus:
        if progress is not None:
            progress("ready")
        return self.status_snapshot()


def build_settings_provider_and_ocr(_context: ScenarioContext) -> ScenarioHandle:
    root = QWidget()
    layout = QHBoxLayout(root)
    settings = LLMSettings(
        providers=[LLMProviderConfig(
            key="synthetic", display_name="Synthetic provider",
            base_url="https://synthetic.invalid/v1", api_key="",
            models=["fast", "reasoning"],
        )],
        default_fq_model_key="synthetic/fast",
    )
    editor = ProviderSettingsEditor(settings, root)
    ocr = OcrSettingsCard(_SyntheticOcr(), root)
    layout.addWidget(editor, 2)
    status_column = QVBoxLayout()
    status_column.addWidget(ocr)
    status_column.addStretch(1)
    layout.addLayout(status_column, 1)
    ocr.activate()
    return ScenarioHandle(root, lambda: ocr.status is not None, ocr.shutdown)
