from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class FileDropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("fileDropZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)

        title = QLabel("Drop a dataset file here")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")

        subtitle = QLabel("Supports .csv, .xlsx, and .xls")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        mime_data = event.mimeData()
        if mime_data is not None and any(url.isLocalFile() for url in mime_data.urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        mime_data = event.mimeData()
        if mime_data is None:
            event.ignore()
            return

        for url in mime_data.urls():
            if url.isLocalFile():
                self.file_dropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()
