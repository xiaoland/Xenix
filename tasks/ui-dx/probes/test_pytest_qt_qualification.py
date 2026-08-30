from __future__ import annotations

from PySide6.QtCore import QTimer, QtMsgType, qWarning
from PySide6.QtWidgets import QApplication, QLabel


def test_pytest_qt_core_contracts(qapp, qtbot) -> None:
    assert qapp is QApplication.instance()

    label = QLabel("Synthetic UI qualification")
    label.setObjectName("qualificationLabel")
    label.resize(320, 80)
    qtbot.addWidget(label)

    with qtbot.waitExposed(label, timeout=2_000):
        label.show()

    timer = QTimer(label)
    timer.setSingleShot(True)
    with qtbot.waitSignal(timer.timeout, timeout=2_000):
        timer.start(0)

    qtbot.waitUntil(lambda: label.isVisible(), timeout=2_000)
    screenshot = qtbot.screenshot(label, "phase0")

    assert screenshot.suffix == ".png"
    assert screenshot.stat().st_size > 0
    print(f"PYTEST_QT_SCREENSHOT path={screenshot} bytes={screenshot.stat().st_size}")


def test_pytest_qt_captures_qt_logs(qtlog) -> None:
    message = "xenix-ui-dx-phase0-qualification"
    qWarning(message)

    assert any(
        record.type is QtMsgType.QtWarningMsg and record.message.strip() == message
        for record in qtlog.records
    )
