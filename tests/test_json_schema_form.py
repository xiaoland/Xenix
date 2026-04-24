import pytest
from PySide6.QtWidgets import QApplication

from xenix.ui.widgets.json_schema_form import JsonSchemaFormWidget


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_json_schema_form_round_trips_supported_field_shapes(app: QApplication) -> None:
    widget = JsonSchemaFormWidget()
    widget.set_schema(
        {
            "properties": {
                "enabled": {"type": "boolean", "default": True, "title": "Enabled"},
                "count": {"type": "integer", "default": 3, "minimum": 1},
                "weight": {"type": "number", "default": 1.5},
                "mode": {"type": "string", "enum": ["fast", "safe"], "default": "safe"},
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["age", "income"],
                },
                "max_depth": {
                    "title": "Max Depth",
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "default": None,
                },
            }
        }
    )

    bindings = widget._bindings
    bindings["enabled"].widget.setChecked(False)  # type: ignore[union-attr]
    bindings["count"].widget.setValue(7)  # type: ignore[union-attr]
    bindings["weight"].widget.setValue(2.75)  # type: ignore[union-attr]
    bindings["mode"].widget.setCurrentIndex(0)  # type: ignore[union-attr]
    bindings["features"].widget.setPlainText("tenure\nsegment")  # type: ignore[union-attr]
    bindings["max_depth"].widget.setText("5")  # type: ignore[union-attr]

    assert widget.values() == {
        "enabled": False,
        "count": 7,
        "weight": 2.75,
        "mode": "fast",
        "features": ["tenure", "segment"],
        "max_depth": 5,
    }
