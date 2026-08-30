from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from xenix.ui.semantic_identity import identify

from .contracts import ScenarioContext, ScenarioHandle
from .driver import configure_scenario_application
from .registry import get_scenario, list_scenarios


class ScenarioGallery(QMainWindow):
    def __init__(self, context: ScenarioContext, initial_scenario_id: str | None = None) -> None:
        super().__init__()
        self._context = context
        self._active: ScenarioHandle | None = None
        self.setWindowTitle("Xenix Qt Widget Lab")
        self.resize(1180, 820)

        root = QWidget(self)
        layout = QHBoxLayout(root)
        sidebar = QWidget(root)
        sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        self._search = identify(QLineEdit(), "ui-lab.scenario.search")
        self._search.setPlaceholderText("Filter scenarios")
        self._list = identify(QListWidget(), "ui-lab.scenario.list")
        self._description = QLabel()
        self._description.setWordWrap(True)
        sidebar_layout.addWidget(self._search)
        sidebar_layout.addWidget(self._list, 1)
        sidebar_layout.addWidget(self._description)

        self._host = QWidget(root)
        self._host_layout = QVBoxLayout(self._host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(sidebar)
        layout.addWidget(self._host, 1)
        self.setCentralWidget(root)

        self._search.textChanged.connect(self._refill)
        self._list.currentItemChanged.connect(self._activate_item)
        self._refill()
        target = initial_scenario_id or list_scenarios()[0].id
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == target:
                self._list.setCurrentRow(index)
                break

    def closeEvent(self, event: QCloseEvent) -> None:
        self._close_active()
        super().closeEvent(event)

    def _refill(self) -> None:
        selected = self._list.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected is not None else None
        query = self._search.text().strip().casefold()
        self._list.clear()
        for scenario in list_scenarios():
            haystack = f"{scenario.id} {scenario.title} {scenario.description}".casefold()
            if query and query not in haystack:
                continue
            item = QListWidgetItem(f"{scenario.title}\n{scenario.id}")
            item.setData(Qt.ItemDataRole.UserRole, scenario.id)
            self._list.addItem(item)
            if scenario.id == selected_id:
                self._list.setCurrentItem(item)
        if self._list.currentItem() is None and self._list.count():
            self._list.setCurrentRow(0)

    def _activate_item(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        scenario = get_scenario(str(current.data(Qt.ItemDataRole.UserRole)))
        self._close_active()
        configure_scenario_application(self._context.application, scenario)
        self._active = scenario.build(self._context)
        self._active.root.setParent(self._host)
        self._active.root.setMinimumSize(scenario.viewport_width, scenario.viewport_height)
        self._host_layout.addWidget(self._active.root)
        self._active.root.show()
        self._description.setText(scenario.description)

    def _close_active(self) -> None:
        if self._active is None:
            return
        self._host_layout.removeWidget(self._active.root)
        self._active.close()
        self._active = None
