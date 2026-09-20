"""Modeless audit center: explanations first, domain evidence available on demand."""

from __future__ import annotations

import html
import json

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import report_exception
from ..services.audit_contracts import AuditDetail, AuditReference, AuditScope, AuditSummary
from .async_read import AsyncRead
from .semantic_identity import identify


class AuditCenterDialog(QDialog):
    task_requested = Signal(int)
    thread_requested = Signal(int)
    artifact_requested = Signal(str)

    def __init__(self, *, service, thread_id: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._thread_id = thread_id
        self._task_id: int | None = None
        self._limit = 50
        self._items: list[AuditSummary] = []
        self._detail: AuditDetail | None = None
        self._reference: AuditReference | None = None
        self._history: list[tuple[AuditReference, int, tuple[int, ...]]] = []
        self._restore_position: tuple[int, tuple[int, ...]] | None = None
        self._closed = False
        self._list_loading = False
        self._detail_loading = False
        self._list_read = AsyncRead(self)
        self._detail_read = AsyncRead(self)
        self._list_read.loaded.connect(self._on_list)
        self._detail_read.loaded.connect(self._on_detail)
        self.setWindowModality(Qt.NonModal)
        self.resize(1100, 740)
        self._scope = identify(QComboBox(self), "audit.scope")
        self._category = QComboBox(self)
        self._search = QLineEdit(self)
        self._search.setClearButtonEnabled(True)
        self._context = QLabel(self)
        self._refresh = QPushButton(self)
        self._refresh.clicked.connect(self.refresh)
        self._scope.currentIndexChanged.connect(self._filter_changed)
        self._category.currentIndexChanged.connect(self._filter_changed)
        self._search.textChanged.connect(self._filter_changed)
        top = QHBoxLayout()
        top.addWidget(self._scope)
        top.addWidget(self._context, 1)
        top.addWidget(self._refresh)
        self._list = identify(QTableWidget(0, 1, self), "audit.output.list")
        self._list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.horizontalHeader().hide()
        self._list.horizontalHeader().setStretchLastSection(True)
        self._list.verticalHeader().hide()
        self._list.itemSelectionChanged.connect(self._select)
        self._list.itemDoubleClicked.connect(self._open_file)
        self._more = QPushButton(self)
        self._more.clicked.connect(self._load_more)
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._category)
        left_layout.addWidget(self._search)
        left_layout.addWidget(self._list, 1)
        left_layout.addWidget(self._more)
        self._back = QPushButton(self)
        self._back.clicked.connect(self._go_back)
        self._clear_task = QPushButton(self)
        self._clear_task.clicked.connect(self._clear_task_filter)
        self._title = QLabel(self)
        self._title.setWordWrap(True)
        self._title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._state = QLabel(self)
        self._state.setWordWrap(True)
        self._tabs = QTabWidget(self)
        self._pages = [QTextBrowser(self) for _ in range(3)]
        for page in self._pages:
            page.setOpenLinks(False)
            page.anchorClicked.connect(self._activate)
            self._tabs.addTab(page, "")
        identify(self._pages[0], "audit.explanation")
        self._files = QComboBox(self)
        self._open = identify(QPushButton(self), "audit.open-artifact")
        self._open.clicked.connect(self._open_file)
        self._files.currentIndexChanged.connect(self._sync_actions)
        self._job = QPushButton(self)
        self._job.clicked.connect(self._open_task)
        self._thread = QPushButton(self)
        self._thread.clicked.connect(self._open_thread)
        self._raw = QPushButton(self)
        self._raw.setCheckable(True)
        self._raw.toggled.connect(lambda: self._render_detail())
        actions = QHBoxLayout()
        for control in (self._files, self._open, self._job, self._thread):
            actions.addWidget(control)
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        nav = QHBoxLayout()
        nav.addWidget(self._back)
        nav.addWidget(self._clear_task)
        nav.addStretch()
        right_layout.addLayout(nav)
        right_layout.addWidget(self._title)
        right_layout.addWidget(self._state)
        right_layout.addWidget(self._tabs, 1)
        right_layout.addWidget(self._raw)
        right_layout.addLayout(actions)
        splitter = QSplitter(self)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([290, 810])
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh)
        self.retranslate_ui()

    def set_thread_id(self, thread_id: int | None) -> None:
        if self._thread_id == thread_id:
            return
        self._thread_id = thread_id
        if not self._scope.currentData():
            self._filter_changed()

    def focus_task(self, task_id: int) -> None:
        self._task_id = task_id
        self._scope.setCurrentIndex(1)
        self._category.setCurrentIndex(0)
        self._search.clear()
        self._filter_changed()

    def focus_reference(self, reference: AuditReference) -> None:
        if self._reference and self._reference != reference:
            self._history.append(
                (
                    self._reference,
                    self._tabs.currentIndex(),
                    tuple(page.verticalScrollBar().value() for page in self._pages),
                )
            )
        self._load_detail(reference)

    def _clear_task_filter(self) -> None:
        self._task_id = None
        self._filter_changed()

    def _filter_changed(self, *_args) -> None:
        self._limit = 50
        self._history.clear()
        self._restore_position = None
        self._reference = None
        self._detail = None
        self._list_loading = self._detail_loading = False
        self._list_read.invalidate()
        self._detail_read.invalidate()
        self._title.clear()
        self._state.clear()
        self._list.setRowCount(0)
        self._sync_actions()
        for page in self._pages:
            page.clear()
        self.refresh()

    def refresh(self) -> None:
        if self._closed or not self.isVisible() or self._list_loading:
            return
        scope = AuditScope(all_threads=bool(self._scope.currentData()), thread_id=self._thread_id)
        if not scope.all_threads and scope.thread_id is None:
            self._items = []
            self._list.setRowCount(0)
            self._title.setText(self.tr("No current conversation"))
            self._state.setText(self.tr("Open a conversation, or select All conversations."))
            return
        category, search, limit, task_id = (
            self._category.currentData() or "",
            self._search.text(),
            self._limit + 1,
            self._task_id,
        )
        self._list_loading = True
        self._list_read.submit(
            lambda: self._service.list_outputs(scope, category=category, search=search, limit=limit, task_id=task_id)
        )

    def _on_list(self, result: object) -> None:
        self._list_loading = False
        if isinstance(result, Exception):
            self._detail = None
            self._sync_actions()
            self._state.setText(self.tr("Outputs could not be loaded. Retry with Refresh."))
            self._timer.stop()
            report_exception(result)
            return
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()
        self._items = result[: self._limit]
        self._more.setVisible(len(result) > self._limit)
        blocker = QSignalBlocker(self._list)
        self._list.setRowCount(len(self._items))
        selected = 0
        for index, item in enumerate(self._items):
            text = f"{item.title}\n{self._category_label(item.category)} · {item.created_at.astimezone():%m-%d %H:%M}"
            row = QTableWidgetItem(text)
            row.setData(Qt.UserRole, item.reference)
            row.setToolTip(item.title)
            self._list.setItem(index, 0, row)
            self._list.setRowHeight(index, 58)
            if item.reference == self._reference:
                selected = index
        if self._items:
            self._list.selectRow(selected)
        blocker.unblock()
        self._clear_task.setVisible(self._task_id is not None)
        if not self._items:
            self._detail = self._reference = None
            self._detail_read.invalidate()
            self._title.setText(self.tr("No matching outputs"))
            self._state.setText(self.tr("This conversation has no outputs yet, or no outputs match these filters."))
            for page in self._pages:
                page.clear()
            self._sync_actions()
        elif not self._history:
            self._select()
        elif self._reference is not None:
            self._load_detail(self._reference)

    def _select(self) -> None:
        self._history.clear()
        row = self._list.currentRow()
        if row >= 0 and row < len(self._items):
            self._load_detail(self._items[row].reference)

    def _load_detail(self, reference: AuditReference) -> None:
        if self._detail_loading and reference == self._reference:
            return
        if self._reference != reference:
            self._detail = None
            self._state.setText(self.tr("Loading recorded evidence…"))
            self._tabs.setCurrentIndex(0)
            for page in self._pages:
                page.clear()
        self._reference = reference
        self._sync_actions()
        thread_id = self._thread_id if not self._scope.currentData() else None
        self._detail_loading = True
        self._detail_read.submit(lambda: self._service.get_detail(reference, thread_id=thread_id))

    def _on_detail(self, result: object) -> None:
        self._detail_loading = False
        if isinstance(result, Exception):
            self._detail = None
            self._state.setText(self.tr("Evidence could not be loaded. Retry with Refresh."))
            self._sync_actions()
            report_exception(result)
            return
        if self._detail != result:
            self._detail = result
            self._render_detail()
        if self._restore_position is not None:
            tab, positions = self._restore_position
            self._restore_position = None
            self._tabs.setCurrentIndex(tab)
            for page, position in zip(self._pages, positions, strict=True):
                page.verticalScrollBar().setValue(position)

    @staticmethod
    def _text(value: object) -> str:
        return html.escape(str(value)).replace("\n", "<br>")

    def _table(self, values: dict) -> str:
        names = {
            "evaluation": self.tr("Evaluation"),
            "baseline_evaluation": self.tr("Baseline evaluation"),
            "split_facts": self.tr("Data split"),
            "test_rows": self.tr("Test rows"),
            "train_rows": self.tr("Training rows"),
            "row_count": self.tr("Total rows"),
            "rendered_row_count": self.tr("Rendered rows"),
            "truncated": self.tr("Partial data"),
            "warnings": self.tr("Limitations"),
            "error": self.tr("Error"),
            "source_file": self.tr("Source file"),
            "sheet": self.tr("Worksheet"),
            "operation": self.tr("Operation"),
        }
        rows = []
        for key, value in values.items():
            if isinstance(value, dict):
                rendered = self._table(value)
            elif isinstance(value, list):
                rendered = "<br>".join(self._text(item) for item in value)
            elif isinstance(value, bool):
                rendered = self.tr("Yes") if value else self.tr("No")
            else:
                rendered = self._text(value)
            rows.append(
                f"<tr><td valign='top'><b>{self._text(names.get(key, key.replace('_', ' ')))}</b></td><td>{rendered}</td></tr>"
            )
        return "<table width='100%' cellspacing='8'>" + "".join(rows) + "</table>"

    def _render_detail(self) -> None:
        detail = self._detail
        if detail is None:
            return
        positions = [page.verticalScrollBar().value() for page in self._pages]
        summary = detail.summary
        labels = {
            "Why this approach": self.tr("Why this approach"),
            "Not recorded": self.tr("Not recorded"),
            "What the result means": self.tr("What the result means"),
            "Agent-authored interpretation; inspect the recorded evidence.": self.tr(
                "Agent-authored interpretation; inspect the recorded evidence."
            ),
            "View evidence": self.tr("View evidence"),
            "Earlier and other-conversation interpretations": self.tr("Earlier and other-conversation interpretations"),
            "Limitations": self.tr("Limitations"),
            "Recorded evidence": self.tr("Recorded evidence"),
            "Inputs and source": self.tr("Inputs and source"),
            "No upstream inputs recorded.": self.tr("No upstream inputs recorded."),
            "Not recorded / not applicable": self.tr("Not recorded / not applicable"),
        }
        self._title.setText(summary.title)
        self._context.setText(
            summary.thread_title
            or (f"#{summary.thread_id}" if summary.thread_available else self.tr("Source conversation unavailable"))
        )
        if detail.explanations:
            state = self.tr("Agent interpretation recorded")
        elif summary.status in {"pending", "running"}:
            state = self.tr("Waiting for task results; no interpretation yet.")
        elif summary.rationale:
            state = self.tr("Output available; the Agent has not interpreted it yet.")
        else:
            state = self.tr("No Agent explanation was saved for this output.")
        statuses = {
            "pending": self.tr("Queued"),
            "running": self.tr("Running"),
            "succeeded": self.tr("Succeeded"),
            "failed": self.tr("Failed"),
            "cancelled": self.tr("Cancelled"),
        }
        self._state.setText(
            state
            + (
                " · " + self.tr("Task: {status}").format(status=statuses.get(summary.status, summary.status))
                if summary.status
                else ""
            )
        )
        body = f"<h3>{labels['Why this approach']}</h3><p>{self._text(summary.rationale or labels['Not recorded'])}</p>"
        if detail.explanations:
            interpretation = detail.explanations[0]
            body += f"<h3>{labels['What the result means']}</h3><p>{self._text(interpretation.text)}</p>"
            body += f"<p><small>{labels['Agent-authored interpretation; inspect the recorded evidence.']} · {interpretation.created_at.astimezone():%Y-%m-%d %H:%M}</small></p>"
            for ref in interpretation.evidence:
                body += f"<p><a href='audit:{ref.kind}:{ref.id}'>{labels['View evidence']}: {ref.key}</a></p>"
            if len(detail.explanations) > 1 and self._raw.isChecked():
                body += f"<h3>{labels['Earlier and other-conversation interpretations']}</h3>"
                for old in detail.explanations[1:]:
                    body += f"<p>{old.created_at.astimezone():%Y-%m-%d %H:%M} · {old.thread_id}<br>{self._text(old.text)}</p>"
        else:
            body += f"<h3>{labels['What the result means']}</h3><p>{state}</p>"
        evidence = detail.evidence
        graph = evidence.get("analysis_graph", {})
        if graph.get("truncated") or graph.get("warnings"):
            body += f"<h3>{labels['Limitations']}</h3>" + self._table(
                {
                    key: graph[key]
                    for key in ("row_count", "rendered_row_count", "truncated", "warnings")
                    if key in graph
                }
            )
        evaluation = evidence.get("evaluation", evidence)
        facts = {
            key: evaluation[key]
            for key in ("evaluation", "baseline_evaluation", "comparison", "split_facts", "error")
            if key in evaluation
        }
        if facts:
            body += f"<h3>{labels['Recorded evidence']}</h3>" + self._table(facts)
        if self._raw.isChecked():
            body += "<pre>" + html.escape(json.dumps(evidence, ensure_ascii=False, indent=2, default=str)) + "</pre>"
        self._pages[0].setHtml(body)
        inputs = f"<h3>{labels['Inputs and source']}</h3>"
        for item in detail.inputs:
            inputs += f"<p>{self._text(item.role)} · <a href='audit:{item.reference.kind}:{item.reference.id}'>{self._text(item.title)}</a></p>"
        if not detail.inputs:
            inputs += f"<p>{labels['No upstream inputs recorded.']}</p>"
        inputs += self._table(
            {key: value for key, value in evidence.items() if key in {"source_file", "sheet", "operation"}}
        )
        self._pages[1].setHtml(inputs)
        parameters = ""
        for title, values in (
            (self.tr("Submitted parameters"), detail.submitted_parameters),
            (self.tr("Effective parameters"), detail.effective_parameters),
            (self.tr("Selected tuning parameters"), detail.selected_parameters),
        ):
            parameters += f"<h3>{title}</h3>" + (
                self._table(values) if values else f"<p>{labels['Not recorded / not applicable']}</p>"
            )
        self._pages[2].setHtml(parameters)
        for page, position in zip(self._pages, positions, strict=True):
            page.verticalScrollBar().setValue(position)
        selected_file = self._files.currentData()
        blocker = QSignalBlocker(self._files)
        self._files.clear()
        for file in detail.files:
            self._files.addItem(
                file.title + ("" if file.available else " · " + self.tr("File unavailable")), file.artifact_id
            )
        self._files.setCurrentIndex(max(0, self._files.findData(selected_file)))
        blocker.unblock()
        self._back.setVisible(bool(self._history))
        self._sync_actions()

    def _activate(self, url: QUrl) -> None:
        parts = url.toString().split(":")
        if len(parts) == 3 and parts[0] == "audit":
            self.focus_reference(AuditReference(kind=parts[1], id=int(parts[2])))

    def _go_back(self) -> None:
        if self._history:
            reference, tab, positions = self._history.pop()
            self._restore_position = (tab, positions)
            self._load_detail(reference)

    def _sync_actions(self, *_args) -> None:
        detail = self._detail
        self._back.setVisible(bool(self._history))
        self._open.setEnabled(
            bool(
                detail
                and any(file.artifact_id == self._files.currentData() and file.available for file in detail.files)
            )
        )
        self._job.setEnabled(bool(detail and detail.summary.task_id))
        self._thread.setEnabled(bool(detail and detail.summary.thread_id and detail.summary.thread_available))

    def _open_file(self, *_args) -> None:
        if self._open.isEnabled():
            self.artifact_requested.emit(f"artifact://{self._files.currentData()}")

    def _open_task(self) -> None:
        if self._detail and self._detail.summary.task_id:
            self.task_requested.emit(self._detail.summary.task_id)

    def _open_thread(self) -> None:
        if self._detail and self._detail.summary.thread_id:
            self.thread_requested.emit(self._detail.summary.thread_id)

    def _load_more(self) -> None:
        self._limit += 50
        self.refresh()

    def _category_label(self, category: str) -> str:
        return {
            "dataset": self.tr("Dataset"),
            "model": self.tr("Model"),
            "chart": self.tr("Chart"),
            "report": self.tr("Report"),
            "application": self.tr("Application result"),
            "artifact": self.tr("Other output"),
        }.get(category, category)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Audit Center"))
        scope, category = self._scope.currentData(), self._category.currentData()
        blockers = [QSignalBlocker(self._scope), QSignalBlocker(self._category)]
        self._scope.clear()
        self._scope.addItem(self.tr("Current conversation"), False)
        self._scope.addItem(self.tr("All conversations"), True)
        self._scope.setCurrentIndex(1 if scope else 0)
        self._category.clear()
        self._category.addItem(self.tr("All output types"), "")
        for value in ("dataset", "model", "chart", "report", "application", "artifact"):
            self._category.addItem(self._category_label(value), value)
        self._category.setCurrentIndex(max(0, self._category.findData(category)))
        for blocker in blockers:
            blocker.unblock()
        self._search.setPlaceholderText(self.tr("Search outputs"))
        for button, label in (
            (self._refresh, self.tr("Refresh")),
            (self._more, self.tr("Load more")),
            (self._back, self.tr("Back to output")),
            (self._clear_task, self.tr("Clear task filter")),
            (self._raw, self.tr("Show original records and interpretation history")),
            (self._open, self.tr("Open output")),
            (self._job, self.tr("View task")),
            (self._thread, self.tr("Source conversation")),
        ):
            button.setText(label)
        for index, label in enumerate(
            (self.tr("Explanation and evidence"), self.tr("Inputs and source"), self.tr("Parameters and records"))
        ):
            self._tabs.setTabText(index, label)
        self._back.setVisible(bool(self._history))
        self._clear_task.setVisible(self._task_id is not None)
        self._more.hide()
        self._sync_actions()
        self._render_detail()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        self._list_read.invalidate()
        self._detail_read.invalidate()
        self._list_loading = self._detail_loading = False
        super().hideEvent(event)

    def shutdown(self) -> None:
        self._closed = True
        self._timer.stop()
        self._list_read.shutdown()
        self._detail_read.shutdown()
