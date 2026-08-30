from __future__ import annotations

import argparse
import json

from PySide6.QtWidgets import QApplication

from .contracts import ScenarioContext
from .gallery import ScenarioGallery
from .registry import get_scenario, list_scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Xenix Qt Widget Lab")
    parser.add_argument("scenario", nargs="?", help="Scenario ID to open")
    parser.add_argument("--list", action="store_true", help="List admitted scenarios")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args()

    if args.list:
        metadata = [scenario.metadata() for scenario in list_scenarios()]
        if args.json:
            print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        else:
            for scenario in list_scenarios():
                print(f"{scenario.id}\t{scenario.title}")
        return 0

    if args.scenario is not None:
        get_scenario(args.scenario)
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication(["xenix-ui-lab"])
    app.setApplicationName("Xenix Qt Widget Lab")
    gallery = ScenarioGallery(ScenarioContext(app), args.scenario)
    gallery.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
