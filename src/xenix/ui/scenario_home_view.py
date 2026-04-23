from __future__ import annotations

from functools import partial

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..services.analysis_scenario_service import AnalysisScenario, AnalysisScenarioAvailability
from .analysis_scenario_text import (
    localized_analysis_scenario_description,
    localized_analysis_scenario_display_name,
    localized_analysis_scenario_status,
)


class ScenarioHomeView(QWidget):
    scenario_selected = Signal(str)
    open_settings_requested = Signal()
    open_history_requested = Signal()

    def __init__(self, analysis_scenarios: list[AnalysisScenario], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis_scenarios = analysis_scenarios

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._cards_label = QLabel()
        self._history_button = QPushButton()
        self._settings_button = QPushButton()
        self._analysis_buttons: dict[str, QPushButton] = {}
        self._analysis_descriptions: dict[str, QLabel] = {}
        self._analysis_statuses: dict[str, QLabel] = {}

        self._build_ui()
        self.retranslate_ui()
        self._refresh_scenario_state()

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
        layout.addLayout(self._build_analysis_cards())

        utility_layout = QHBoxLayout()
        utility_layout.setSpacing(12)
        self._history_button.clicked.connect(self.open_history_requested)
        self._settings_button.clicked.connect(self.open_settings_requested)
        utility_layout.addWidget(self._history_button)
        utility_layout.addWidget(self._settings_button)
        utility_layout.addStretch(1)
        layout.addLayout(utility_layout)
        layout.addStretch(1)

    def _build_analysis_cards(self) -> QGridLayout:
        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(16)
        cards_layout.setVerticalSpacing(16)

        for index, scenario in enumerate(self._analysis_scenarios):
            card = QFrame(self)
            card.setFrameShape(QFrame.StyledPanel)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(10)

            button = QPushButton()
            button.setMinimumHeight(44)
            button.clicked.connect(partial(self._handle_analysis_selection, scenario.key))

            description = QLabel()
            description.setWordWrap(True)

            status = QLabel()
            status.setWordWrap(True)
            status.setStyleSheet("font-size: 12px; color: #5b5b5b;")

            card_layout.addWidget(button)
            card_layout.addWidget(description)
            card_layout.addWidget(status)
            cards_layout.addWidget(card, index // 2, index % 2)

            self._analysis_buttons[scenario.key] = button
            self._analysis_descriptions[scenario.key] = description
            self._analysis_statuses[scenario.key] = status

        return cards_layout

    def retranslate_ui(self) -> None:
        self._title_label.setText(self.tr("Xenix native ML workspace"))
        self._summary_label.setText(
            self.tr(
                "Choose a guided scenario to prepare data, train models, and run local prediction without technical tabs."
            )
        )
        self._cards_label.setText(self.tr("Analysis Scenarios"))
        self._history_button.setText(self.tr("History"))
        self._settings_button.setText(self.tr("Settings"))

        for scenario in self._analysis_scenarios:
            self._analysis_buttons[scenario.key].setText(localized_analysis_scenario_display_name(scenario))
            self._analysis_descriptions[scenario.key].setText(localized_analysis_scenario_description(scenario))
            self._analysis_statuses[scenario.key].setText(localized_analysis_scenario_status(scenario))

        self._refresh_scenario_state()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def _handle_analysis_selection(self, scenario_key: str) -> None:
        self.scenario_selected.emit(scenario_key)

    def _refresh_scenario_state(self) -> None:
        for scenario in self._analysis_scenarios:
            button = self._analysis_buttons[scenario.key]
            button.setEnabled(scenario.availability is AnalysisScenarioAvailability.AVAILABLE)
