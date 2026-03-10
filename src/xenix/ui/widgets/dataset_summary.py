from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QFrame, QLabel

from ...services.dataset_inspection import DatasetInspection


class DatasetSummaryWidget(QFrame):
    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._layout = QFormLayout(self)

        self._file_name = QLabel("-")
        self._file_path = QLabel("-")
        self._source_format = QLabel("-")
        self._row_count = QLabel("-")
        self._column_count = QLabel("-")

        self._file_path.setWordWrap(True)

        self._layout.addRow("File", self._file_name)
        self._layout.addRow("Path", self._file_path)
        self._layout.addRow("Format", self._source_format)
        self._layout.addRow("Rows", self._row_count)
        self._layout.addRow("Columns", self._column_count)

    def clear(self) -> None:
        self._file_name.setText("-")
        self._file_path.setText("-")
        self._source_format.setText("-")
        self._row_count.setText("-")
        self._column_count.setText("-")

    def set_inspection(self, inspection: DatasetInspection) -> None:
        self._file_name.setText(inspection.file_name)
        self._file_path.setText(inspection.source_path)
        self._source_format.setText(inspection.source_format.value)
        self._row_count.setText(str(inspection.row_count))
        self._column_count.setText(str(inspection.column_count))
