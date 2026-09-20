from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QRunnable, QSignalBlocker, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QTextBrowser,
)

from ..exceptions import report_exception
from ..services.audit_contracts import AuditScope
from .async_read import AsyncRead
from .widgets.task_log_view import TaskLogView
from ..services.job_scheduler import JobScheduler
from ..services.job_service import JobDomain, JobItem, JobQueryService, JobStatus

JOB_POLL_INTERVAL_MS = 2_000
JOB_PAGE_SIZE = 50


class _JobLoadSignals(QObject):
    finished = Signal(int, object)


class _JobLoad(QRunnable):
    def __init__(
        self,
        service: JobQueryService,
        generation: int,
        domain: JobDomain | None,
        status: JobStatus | None,
        search: str,
        limit: int,
        scope: AuditScope,
    ) -> None:
        super().__init__()
        self._service = service
        self._generation = generation
        self._domain = domain
        self._status = status
        self._search = search
        self._limit = limit
        self._scope = scope
        self.signals = _JobLoadSignals()

    def run(self) -> None:
        try:
            result: object = self._service.list_jobs(
                domain=self._domain,
                status=self._status,
                search=self._search,
                limit=self._limit,
                scope=self._scope,
            )
        except Exception as exc:
            logging.getLogger(__name__).exception("Background read failed")
            result = exc
        self.signals.finished.emit(self._generation, result)


class JobCenterDialog(QDialog):
    """Scoped job state and logs; domain services retain execution authority."""

    output_requested = Signal(int)
    thread_requested = Signal(int)

    def __init__(
        self,
        service: JobQueryService,
        *,
        scheduler: JobScheduler | None = None,
        ml_service=None,
        thread_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._service = service
        self._ml_service = ml_service
        self._thread_id = thread_id
        self._focus_reference: str | None = None
        self._shown_reference: str | None = None
        self._details_read = AsyncRead(self)
        self._details_read.loaded.connect(self._details_loaded)
        self._scheduler = scheduler
        self._thread_pool = QThreadPool(self)
        self._generation = 0
        self._limit = JOB_PAGE_SIZE
        self._load: _JobLoad | None = None
        self._load_pending = False
        self._active = False
        self._shutdown = False

        self._scope_filter = QComboBox(self)
        self._scope_filter.setAccessibleIdentifier("jobs.scope")
        self._scope_filter.currentIndexChanged.connect(self._filters_changed)
        self._domain_filter = QComboBox(self)
        self._domain_filter.currentIndexChanged.connect(self._filters_changed)
        self._status_filter = QComboBox(self)
        self._status_filter.currentIndexChanged.connect(self._filters_changed)
        self._search = QLineEdit(self)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filters_changed)

        self._table = QTableWidget(0, 6, self)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (0, 1, 3, 4):
            self._table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemDoubleClicked.connect(self._show_details)

        self._summary = QLabel(self)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self._cancel_selected_job)
        self._refresh_button = QPushButton(self)
        self._refresh_button.clicked.connect(self.refresh)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)
        self._load_more_button = QPushButton(self)
        self._load_more_button.clicked.connect(self._load_more)
        self._load_more_button.setVisible(False)
        self._table.itemSelectionChanged.connect(self._update_action_buttons)
        self._table.itemSelectionChanged.connect(self._show_details)
        self._detail = QTextBrowser(self)
        self._detail.setMaximumHeight(130)
        self._logs = TaskLogView(self)
        self._logs.setMaximumHeight(160)
        self._source_button = QPushButton(self)
        self._source_button.clicked.connect(self._open_source)
        self._outputs_button = QPushButton(self)
        self._outputs_button.clicked.connect(self._open_outputs)

        filters = QHBoxLayout()
        filters.addWidget(self._scope_filter)
        filters.addWidget(self._domain_filter)
        filters.addWidget(self._status_filter)
        filters.addWidget(self._search, 1)
        actions = QHBoxLayout()
        actions.addWidget(self._summary)
        actions.addWidget(self._load_more_button)
        actions.addStretch(1)
        actions.addWidget(self._source_button)
        actions.addWidget(self._outputs_button)
        actions.addWidget(self._cancel_button)
        actions.addWidget(self._refresh_button)
        actions.addWidget(self._close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._detail)
        layout.addWidget(self._logs)
        layout.addLayout(actions)
        self.resize(1100, 740)
        self.retranslate_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(JOB_POLL_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh)

    def refresh(self) -> None:
        if self._shutdown or not self._active:
            return
        if self._load is not None:
            self._load_pending = True
            return
        load = _JobLoad(
            self._service,
            self._generation,
            self._domain_filter.currentData(),
            self._status_filter.currentData(),
            self._search.text(),
            self._limit + 1,
            AuditScope(all_threads=bool(self._scope_filter.currentData()), thread_id=self._thread_id),
        )
        load.signals.finished.connect(self._on_loaded)
        self._load = load
        self._thread_pool.start(load)

    def _load_more(self) -> None:
        self._limit += JOB_PAGE_SIZE
        self._generation += 1
        self.refresh()

    def _filters_changed(self, *_args: object) -> None:
        self._generation += 1
        self._details_read.invalidate()
        self._detail.clear()
        self._logs.clear()
        self._table.setRowCount(0)
        self._update_action_buttons()
        self._limit = JOB_PAGE_SIZE
        self.refresh()

    def _on_loaded(self, generation: int, result: object) -> None:
        self._load = None
        if generation != self._generation or not self._active:
            if self._active:
                self._load_pending = False
                self.refresh()
            return
        if isinstance(result, Exception):
            self._summary.setText(self.tr("Jobs could not be loaded."))
            self._load_pending = False
            self._refresh_timer.stop()
            report_exception(result)
            return
        elif isinstance(result, list):
            if not self._refresh_timer.isActive():
                self._refresh_timer.start()
            self._render_jobs(result)
            self._update_action_buttons()
        if self._load_pending:
            self._load_pending = False
            self.refresh()

    def _render_jobs(self, jobs: list[JobItem]) -> None:
        has_more = len(jobs) > self._limit
        jobs = jobs[: self._limit]
        selected = self._focus_reference or self._selected_reference()
        self._table.blockSignals(True)
        self._table.setRowCount(len(jobs))
        selected_row = -1
        for row_index, job in enumerate(jobs):
            values = (
                self._translated_domain(job.domain),
                self._translated_kind(job.kind),
                job.target,
                self._translated_status(job.status),
                job.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                job.thread_title
                or (self.tr("Global") if job.domain is JobDomain.KNOWLEDGE else self.tr("Source not recorded")),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, job)
                self._table.setItem(row_index, column, item)
            if job.reference == selected:
                selected_row = row_index
        if selected_row >= 0:
            self._table.selectRow(selected_row)
        elif jobs:
            self._table.selectRow(0)
        self._table.blockSignals(False)
        if selected_row >= 0:
            self._focus_reference = None
        self._update_action_buttons()
        self._show_details()
        active_count = sum(job.active for job in jobs)
        failed_count = sum(job.status is JobStatus.FAILED for job in jobs)
        self._summary.setText(
            self.tr("%1 jobs · %2 active · %3 failed")
            .replace("%1", str(len(jobs)))
            .replace("%2", str(active_count))
            .replace("%3", str(failed_count))
        )
        self._load_more_button.setVisible(has_more)

    def _selected_job(self) -> JobItem | None:
        row = self._table.currentRow()
        item = self._table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return value if isinstance(value, JobItem) else None

    def _selected_reference(self) -> str | None:
        job = self._selected_job()
        return job.reference if job is not None else None

    def _update_action_buttons(self) -> None:
        job = self._selected_job()
        can_cancel = False
        if job is not None and self._scheduler is not None:
            can_cancel = self._scheduler.capabilities(
                job.domain,
                job.raw_reference,
            ).can_cancel
        self._cancel_button.setEnabled(can_cancel)
        self._source_button.setEnabled(bool(job and job.thread_id and job.thread_title))
        self._outputs_button.setEnabled(bool(job and job.domain is JobDomain.ML))

    def _cancel_selected_job(self) -> None:
        job = self._selected_job()
        if job is None or self._scheduler is None:
            return
        self._scheduler.request_cancel(job.domain, job.raw_reference)
        self.refresh()

    def _show_details(self, *_args: object) -> None:
        job = self._selected_job()
        if job is None:
            self._detail.clear()
            self._logs.clear()
            return
        if self._shown_reference != job.reference:
            self._logs.clear()
        self._shown_reference = job.reference
        details = self.tr("Reference: %1\nDomain: %2\nType: %3\nTarget: %4\nStatus: %5\nPhase: %6\nUpdated: %7")
        values = (
            job.reference,
            self._translated_domain(job.domain),
            self._translated_kind(job.kind),
            job.target,
            self._translated_status(job.status),
            job.phase.replace("_", " "),
            job.updated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        )
        for index, value in enumerate(values, 1):
            details = details.replace(f"%{index}", value)
        if job.error_summary:
            details = self.tr("\nError: %1").replace("%1", job.error_summary).strip() + "\n" + details
        if job.started_at:
            details += self.tr("\nStarted: {time}").format(time=job.started_at.astimezone().isoformat())
        if job.finished_at:
            details += self.tr("\nFinished: {time}").format(time=job.finished_at.astimezone().isoformat())
        self._detail.setPlainText(details)
        self._details_read.invalidate()
        if job.domain is JobDomain.ML and self._ml_service is not None:
            task_id = job.raw_reference
            self._details_read.submit(lambda: self._ml_service.get_task_details(task_id))
        else:
            self._logs.clear()

    def set_thread_id(self, thread_id: int | None) -> None:
        self._thread_id = thread_id
        if not self._scope_filter.currentData():
            self._filters_changed()

    def focus_task(self, task_id: int) -> None:
        self._focus_reference = f"ml:{task_id}"
        self._scope_filter.setCurrentIndex(1)
        self._domain_filter.setCurrentIndex(0)
        self._status_filter.setCurrentIndex(0)
        self._search.setText(f"ml:{task_id}")
        self.refresh()

    def _details_loaded(self, result: object) -> None:
        if not self._active:
            return
        if isinstance(result, Exception):
            self._logs.clear()
            self._detail.append(self.tr("Task logs could not be loaded."))
            report_exception(result)
        else:
            self._logs.set_logs(result.logs)
            self._outputs_button.setEnabled(bool(result.artifacts))

    def _open_source(self) -> None:
        job = self._selected_job()
        if job and job.thread_id:
            self.thread_requested.emit(job.thread_id)

    def _open_outputs(self) -> None:
        job = self._selected_job()
        if job and job.domain is JobDomain.ML:
            self.output_requested.emit(job.raw_reference)

    def _translated_domain(self, domain: JobDomain) -> str:
        return {
            JobDomain.KNOWLEDGE: self.tr("Knowledge"),
            JobDomain.ML: self.tr("Machine learning"),
        }[domain]

    def _translated_status(self, status: JobStatus) -> str:
        return {
            JobStatus.QUEUED: self.tr("Queued"),
            JobStatus.RUNNING: self.tr("Running"),
            JobStatus.SUCCEEDED: self.tr("Succeeded"),
            JobStatus.FAILED: self.tr("Failed"),
            JobStatus.CANCELLED: self.tr("Cancelled"),
        }[status]

    def _translated_kind(self, kind: str) -> str:
        return {
            "import": self.tr("Import"),
            "content_preparation": self.tr("Content preparation"),
            "index_build": self.tr("Index build"),
            "fit": self.tr("Model training"),
            "hyperparameter_tuning": self.tr("Parameter tuning"),
            "evaluate": self.tr("Evaluation"),
            "apply": self.tr("Apply model"),
        }.get(kind, kind.replace("_", " "))

    def retranslate_ui(self) -> None:
        scope = self._scope_filter.currentData()
        blocker = QSignalBlocker(self._scope_filter)
        self._scope_filter.clear()
        self._scope_filter.addItem(self.tr("Current conversation"), False)
        self._scope_filter.addItem(self.tr("All conversations"), True)
        self._scope_filter.setCurrentIndex(1 if scope else 0)
        blocker.unblock()
        selected_domain = self._domain_filter.currentData()
        selected_status = self._status_filter.currentData()
        domain_blocker = QSignalBlocker(self._domain_filter)
        status_blocker = QSignalBlocker(self._status_filter)
        self.setWindowTitle(self.tr("Jobs"))
        self._domain_filter.clear()
        self._domain_filter.addItem(self.tr("All services"), None)
        self._domain_filter.addItem(self.tr("Knowledge"), JobDomain.KNOWLEDGE)
        self._domain_filter.addItem(self.tr("Machine learning"), JobDomain.ML)
        self._status_filter.clear()
        self._status_filter.addItem(self.tr("All statuses"), None)
        for status in JobStatus:
            self._status_filter.addItem(self._translated_status(status), status)
        self._restore_filter(self._domain_filter, selected_domain)
        self._restore_filter(self._status_filter, selected_status)
        domain_blocker.unblock()
        status_blocker.unblock()
        self._search.setPlaceholderText(self.tr("Search jobs"))
        self._table.setHorizontalHeaderLabels(
            [
                self.tr("Service"),
                self.tr("Type"),
                self.tr("Target"),
                self.tr("Status"),
                self.tr("Updated"),
                self.tr("Conversation"),
            ]
        )
        self._source_button.setText(self.tr("Source conversation"))
        self._outputs_button.setText(self.tr("View outputs"))
        self._cancel_button.setText(self.tr("Cancel"))
        self._refresh_button.setText(self.tr("Refresh"))
        self._close_button.setText(self.tr("Close"))
        self._load_more_button.setText(self.tr("Load more"))
        self._update_action_buttons()

    @staticmethod
    def _restore_filter(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    def showEvent(self, event: QShowEvent) -> None:
        self._active = True
        self.refresh()
        self._refresh_timer.start()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        self._active = False
        self._generation += 1
        self._details_read.invalidate()
        self._refresh_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._active = False
        self._generation += 1
        self._details_read.invalidate()
        self._refresh_timer.stop()
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
            self.refresh()
        super().changeEvent(event)

    def shutdown(self) -> None:
        self._shutdown = True
        self._active = False
        self._generation += 1
        self._refresh_timer.stop()
        self._thread_pool.clear()
        self._thread_pool.waitForDone()
        self._details_read.shutdown()


__all__ = ["JOB_PAGE_SIZE", "JOB_POLL_INTERVAL_MS", "JobCenterDialog"]
