from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from ..services.analysis_scenario_service import AnalysisScenario, AnalysisScenarioAvailability
from .analysis_scenario_text import (
    localized_analysis_scenario_description,
    localized_analysis_scenario_display_name,
)


class PreviousModelFlowDialog(QDialog):
    def __init__(
        self,
        scenario: AnalysisScenario,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scenario = scenario

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._scenario_label = QLabel()
        self._detail_label = QLabel()
        self._close_button = QPushButton()

        self.resize(560, 320)
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        self._summary_label.setWordWrap(True)
        self._scenario_label.setWordWrap(True)
        self._detail_label.setWordWrap(True)

        self._close_button.clicked.connect(self.close)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._scenario_label)
        layout.addWidget(self._detail_label)
        layout.addStretch(1)
        layout.addWidget(self._close_button)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Choose Previous Model"))
        self._title_label.setText(self.tr("Choose Previous Model"))
        self._summary_label.setText(
            self.tr("This 2.0 entry reserves the saved-model workflow for the selected analysis scenario.")
        )
        self._scenario_label.setText(
            self.tr("Selected scenario: {scenario_name}").format(
                scenario_name=localized_analysis_scenario_display_name(self._scenario)
            )
        )
        if self._scenario.availability is AnalysisScenarioAvailability.AVAILABLE:
            self._detail_label.setText(
                self.tr(
                    "Saved-model browsing for this scenario will be connected in the next work package.\n\nCurrent scenario description: {description}"
                ).format(
                    description=localized_analysis_scenario_description(self._scenario)
                )
            )
        else:
            self._detail_label.setText(
                self.tr(
                    "This analysis scenario stays in the planned set for the current build.\n\nCurrent scenario description: {description}"
                ).format(
                    description=localized_analysis_scenario_description(self._scenario)
                )
            )
        self._close_button.setText(self.tr("Close"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
