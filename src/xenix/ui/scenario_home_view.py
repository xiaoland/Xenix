from __future__ import annotations

from functools import partial

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..services.scenario_template_service import ScenarioTemplate
from .scenario_template_text import localized_template_description, localized_template_display_name


class ScenarioHomeView(QWidget):
    scenario_selected = Signal(str)
    open_settings_requested = Signal()
    open_history_requested = Signal()

    def __init__(self, templates: list[ScenarioTemplate], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._templates = templates
        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._cards_label = QLabel()
        self._history_button = QPushButton()
        self._settings_button = QPushButton()
        self._scenario_buttons: dict[str, QPushButton] = {}
        self._scenario_descriptions: dict[str, QLabel] = {}

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        self._title_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        self._summary_label.setWordWrap(True)
        self._cards_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._cards_label)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(16)
        cards_layout.setVerticalSpacing(16)
        for index, template in enumerate(self._templates):
            card = QFrame(self)
            card.setFrameShape(QFrame.StyledPanel)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(10)

            button = QPushButton()
            button.setMinimumHeight(44)
            button.clicked.connect(partial(self.scenario_selected.emit, template.key))
            description = QLabel()
            description.setWordWrap(True)

            card_layout.addWidget(button)
            card_layout.addWidget(description)
            cards_layout.addWidget(card, index // 2, index % 2)
            self._scenario_buttons[template.key] = button
            self._scenario_descriptions[template.key] = description

        layout.addLayout(cards_layout)

        utility_layout = QHBoxLayout()
        utility_layout.setSpacing(12)
        self._history_button.clicked.connect(self.open_history_requested)
        self._settings_button.clicked.connect(self.open_settings_requested)
        utility_layout.addWidget(self._history_button)
        utility_layout.addWidget(self._settings_button)
        utility_layout.addStretch(1)
        layout.addLayout(utility_layout)
        layout.addStretch(1)

    def retranslate_ui(self) -> None:
        self._title_label.setText(self.tr("Xenix native ML workspace"))
        self._summary_label.setText(
            self.tr(
                "Choose a guided scenario to prepare data, train models, and run local prediction without technical tabs."
            )
        )
        self._cards_label.setText(self.tr("Scenario Templates"))
        self._history_button.setText(self.tr("History"))
        self._settings_button.setText(self.tr("Settings"))
        for template in self._templates:
            self._scenario_buttons[template.key].setText(localized_template_display_name(template))
            self._scenario_descriptions[template.key].setText(localized_template_description(template))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
