from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from ...services.ai_providers import AIModelOption


def replace_model_options(
    selector: QComboBox,
    options: list[AIModelOption],
    selected_key: str,
    *,
    blank_label: str | None = None,
) -> None:
    selector.clear()
    if blank_label is not None:
        selector.addItem(blank_label, "")
    for option in options:
        selector.addItem(option.label, option.fq_model_key)
    index = selector.findData(selected_key)
    selector.setCurrentIndex(index if index >= 0 else 0)
