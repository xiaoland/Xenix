from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from ..datetime_utils import format_datetime_for_display
from ..services.scenario_model_source_service import CompatibleTrainedModelOption
from ..services.scenario_template_service import ScenarioTemplate
from .native_widgets import emphasize_label
from .scenario_template_text import localized_template_display_name


class PreviousModelFlowDialog(QDialog):
    def __init__(
        self,
        template: ScenarioTemplate,
        selected_model: CompatibleTrainedModelOption | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._selected_model = selected_model

        self._title_label = QLabel()
        self._summary_label = QLabel()
        self._template_label = QLabel()
        self._model_label = QLabel()
        self._detail_label = QLabel()
        self._close_button = QPushButton()

        self.resize(560, 320)
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        emphasize_label(self._title_label, point_delta=2)
        self._summary_label.setWordWrap(True)
        self._template_label.setWordWrap(True)
        self._model_label.setWordWrap(True)
        self._detail_label.setWordWrap(True)

        self._close_button.clicked.connect(self.close)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._template_label)
        layout.addWidget(self._model_label)
        layout.addWidget(self._detail_label)
        layout.addStretch(1)
        layout.addWidget(self._close_button)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Choose Trained Model"))
        self._title_label.setText(self.tr("Choose Trained Model"))
        self._summary_label.setText(
            self.tr("This 2.0 step reserves the trained-model reuse flow after data preparation.")
        )
        self._template_label.setText(
            self.tr("Selected template: {template_name}").format(
                template_name=localized_template_display_name(self._template)
            )
        )
        if self._selected_model is not None:
            self._model_label.setText(
                self.tr("Selected trained model: {model_name}").format(
                    model_name=self._selected_model.model_display_name
                )
            )
            self._detail_label.setText(
                self.tr(
                    "The compatible trained model route is now connected to the second step.\n\nDetailed direct-to-inference reuse will be completed in the next work package.\n\nSource work item: {work_item_name}\nCreated at: {created_at}"
                ).format(
                    work_item_name=self._selected_model.work_item_name,
                    created_at=format_datetime_for_display(
                        self._selected_model.created_at,
                        format_string="%Y-%m-%d %H:%M",
                    ),
                )
            )
        else:
            self._model_label.setText(self.tr("Selected trained model: None"))
            self._detail_label.setText(
                self.tr(
                    "No compatible trained model is currently selected.\n\nThis route will stay available after model selection is connected."
                )
            )
        self._close_button.setText(self.tr("Close"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
