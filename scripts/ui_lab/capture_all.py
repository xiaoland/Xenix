from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts
from xenix.ui.diagnostics.schema import UI_ARTIFACT_SCHEMA_VERSION

from .contracts import ScenarioContext
from .driver import configure_scenario_application, settle_scenario
from .registry import list_scenarios


def capture_all_scenarios(output_root: Path, scenario_ids: list[str] | None = None) -> dict[str, Any]:
    """Capture every admitted scenario from the registry into a fresh run dir.

    Returns a batch manifest. A scenario that fails to build, settle, or capture is
    recorded as a failure and still emits a stage-tagged manifest so the failing
    phase is diagnosable instead of vanishing into a bare traceback.
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(["xenix-ui-capture-all"])
    app.setApplicationName("Xenix UI Capture All")

    available = {scenario.id for scenario in list_scenarios()}
    if scenario_ids is not None:
        unknown = sorted(set(scenario_ids) - available)
        if unknown:
            raise ValueError(f"Unknown UI scenarios: {', '.join(unknown)}")
        expected = list(scenario_ids)
    else:
        expected = [scenario.id for scenario in list_scenarios()]

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = output_root.resolve() / run_id
    captured: list[str] = []
    failures: list[dict[str, str]] = []

    for scenario in list_scenarios():
        if scenario.id not in expected:
            continue
        try:
            handle = scenario.build(ScenarioContext(app))
        except Exception as exc:
            failures.append(_failure(scenario.id, "build", exc))
            _write_failure_manifest(run_dir, scenario.id, "build", exc)
            continue
        try:
            configure_scenario_application(app, scenario)
            handle.root.resize(scenario.viewport_width, scenario.viewport_height)
            handle.root.show()
            settle_scenario(handle.root, handle.readiness)
            destination = run_dir / scenario.id
            capture_ui_artifacts(
                handle.root,
                destination,
                reason="scenario-capture",
                scenario_id=scenario.id,
                policy=CapturePolicy.SYNTHETIC,
            )
            captured.append(scenario.id)
        except Exception as exc:
            stage = "capture" if (run_dir / scenario.id / "manifest.json").exists() else "readiness"
            failures.append(_failure(scenario.id, stage, exc))
            _write_failure_manifest(run_dir, scenario.id, stage, exc)
        finally:
            handle.close()
            handle.root.deleteLater()
            app.processEvents()

    reconciled = not failures and set(expected) == set(captured)
    batch: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "expected_scenarios": sorted(expected),
        "captured_scenarios": sorted(captured),
        "failures": failures,
        "reconciled": reconciled,
    }
    _write_json(run_dir / "batch.json", batch)
    return batch


def _failure(scenario_id: str, stage: str, exc: BaseException) -> dict[str, str]:
    return {
        "scenario_id": scenario_id,
        "stage": stage,
        "error": f"{type(exc).__name__}: {exc}",
    }


def _write_failure_manifest(run_dir: Path, scenario_id: str, stage: str, exc: BaseException) -> None:
    destination = run_dir / scenario_id
    destination.mkdir(parents=True, exist_ok=True)
    _write_json(
        destination / "manifest.json",
        {
            "schema_version": UI_ARTIFACT_SCHEMA_VERSION,
            "reason": "scenario-capture-failure",
            "scenario_id": scenario_id,
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "stage": stage,
            "error": f"{type(exc).__name__}: {exc}",
            "files": [],
        },
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture all admitted Xenix UI scenarios")
    parser.add_argument("--output", type=Path, required=True, help="Artifact output root")
    parser.add_argument("--scenario", action="append", default=None, help="Capture only this scenario (repeatable)")
    args = parser.parse_args()
    batch = capture_all_scenarios(args.output.resolve(), args.scenario)
    print(json.dumps(batch, ensure_ascii=False, sort_keys=True))
    return 0 if batch["reconciled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
