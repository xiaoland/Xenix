from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.job_scheduler import JobScheduler
from ..services.job_service import JobDomain, JobItem, JobQueryService, JobStatus

JOB_POLL_INTERVAL_MS = 2_000


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
    ) -> None:
        super().__init__()
        self._service = service
        self._generation = generation
        self._domain = domain
        self._status = status
        self._search = search
        self.signals = _JobLoadSignals()

    def run(self) -> None:
        try:
            result: object = self._service.list_jobs(
                domain=self._domain,
                status=self._status,
                search=self._search,
            )
        except Exception as exc:
            result = exc
        self.signals.finished.emit(self._generation, result)


class JobCenterDialog(QDialog):
    """Global, read-only view over background jobs owned by product services."""

    def __init__(
        self,
        service: JobQueryService,
        *,
        scheduler: JobScheduler | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._service = service
        self._scheduler = scheduler
        self._thread_pool = QThreadPool(self)
        self._generation = 0
        self._load: _JobLoad | None = None
        self._load_pending = False
        self._active = False
        self._shutdown = False

        self._domain_filter = QComboBox(self)
        self._domain_filter.currentIndexChanged.connect(self._filters_changed)
        self._status_filter = QComboBox(self)
        self._status_filter.currentIndexChanged.connect(self._filters_changed)
        self._search = QLineEdit(self)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filters_changed)

        self._table = QTableWidget(0, 5, self)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (0, 1, 3, 4):
            self._table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemDoubleClicked.connect(self._show_details)

        self._summary = QLabel(self)
        self._details_button = QPushButton(self)
        self._details_button.clicked.connect(self._show_details)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self._cancel_selected_job)
        self._refresh_button = QPushButton(self)
        self._refresh_button.clicked.connect(self.refresh)
        self._close_button = QPushButton(self)
        self._close_button.clicked.connect(self.hide)
        self._table.itemSelectionChanged.connect(self._update_action_buttons)

        filters = QHBoxLayout()
        filters.addWidget(self._domain_filter)
        filters.addWidget(self._status_filter)
        filters.addWidget(self._search, 1)
        actions = QHBoxLayout()
        actions.addWidget(self._summary)
        actions.addStretch(1)
        actions.addWidget(self._details_button)
        actions.addWidget(self._cancel_button)
        actions.addWidget(self._refresh_button)
        actions.addWidget(self._close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self._table, 1)
        layout.addLayout(actions)
        self.resize(860, 480)
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
        )
        load.signals.finished.connect(self._on_loaded)
        self._load = load
        self._thread_pool.start(load)

    def _filters_changed(self, *_args: object) -> None:
        self._generation += 1
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
        elif isinstance(result, list):
            self._render_jobs(result)
            self._update_action_buttons()
        if self._load_pending:
            self._load_pending = False
            self.refresh()

    def _render_jobs(self, jobs: list[JobItem]) -> None:
        selected = self._selected_reference()
        self._table.setRowCount(len(jobs))
        selected_row = -1
        for row_index, job in enumerate(jobs):
            values = (
                self._translated_domain(job.domain),
                self._translated_kind(job.kind),
                job.target,
                self._translated_status(job.status),
                job.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
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
        active_count = sum(job.active for job in jobs)
        failed_count = sum(job.status is JobStatus.FAILED for job in jobs)
        self._summary.setText(
            self.tr("%1 jobs · %2 active · %3 failed")
            .replace("%1", str(len(jobs)))
            .replace("%2", str(active_count))
            .replace("%3", str(failed_count))
        )

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

    def _cancel_selected_job(self) -> None:
        job = self._selected_job()
        if job is None or self._scheduler is None:
            return
        self._scheduler.request_cancel(job.domain, job.raw_reference)
        self.refresh()

    def _show_details(self, *_args: object) -> None:
        job = self._selected_job()
        if job is None:
            return
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
            details += self.tr("\nError: %1").replace("%1", job.error_summary)
        QMessageBox.information(self, self.tr("Job Details"), details)

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
        selected_domain = self._domain_filter.currentData()
        selected_status = self._status_filter.currentData()
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
        self._search.setPlaceholderText(self.tr("Search jobs"))
        self._table.setHorizontalHeaderLabels(
            [
                self.tr("Service"),
                self.tr("Type"),
                self.tr("Target"),
                self.tr("Status"),
                self.tr("Updated"),
            ]
        )
        self._details_button.setText(self.tr("Details"))
        self._cancel_button.setText(self.tr("Cancel"))
        self._refresh_button.setText(self.tr("Refresh"))
        self._close_button.setText(self.tr("Close"))
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
        self._refresh_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._active = False
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


__all__ = ["JOB_POLL_INTERVAL_MS", "JobCenterDialog"]
