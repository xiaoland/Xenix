from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse
import json
from pathlib import Path

from PySide6.QtWidgets import QApplication

from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts

from .contracts import ScenarioContext
from .driver import configure_scenario_application, settle_scenario
from .registry import get_scenario


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one Xenix UI scenario")
    parser.add_argument("scenario", help="Scenario ID")
    parser.add_argument("--output", type=Path, required=True, help="Artifact output root")
    args = parser.parse_args()

    scenario = get_scenario(args.scenario)
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication(["xenix-ui-capture"])
    app.setApplicationName("Xenix UI Capture")
    configure_scenario_application(app, scenario)
    handle = scenario.build(ScenarioContext(app))
    try:
        handle.root.resize(scenario.viewport_width, scenario.viewport_height)
        handle.root.show()
        settle_scenario(handle.root, handle.readiness)
        destination = args.output.resolve() / scenario.id
        manifest = capture_ui_artifacts(
            handle.root,
            destination,
            reason="scenario-capture",
            scenario_id=scenario.id,
            policy=CapturePolicy.SYNTHETIC,
        )
        print(json.dumps({"output": str(destination), "manifest": manifest}, ensure_ascii=False))
        return 0
    finally:
        handle.close()
        handle.root.deleteLater()


if __name__ == "__main__":
    raise SystemExit(main())
