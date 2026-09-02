from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts
from xenix.ui.diagnostics.schema import UI_ARTIFACT_SCHEMA_VERSION

from .contracts import ScenarioContext
from .driver import configure_scenario_application, settle_scenario
from .registry import list_scenarios


def capture_all_scenarios(
    output_root: Path,
    scenario_ids: list[str] | None = None,
    *,
    clean: bool = False,
) -> dict[str, Any]:
    """Capture every admitted scenario from the registry into a fresh run dir.

    Returns a batch manifest. A scenario that fails to build, settle, or capture is
    recorded as a failure and still emits a stage-tagged manifest so the failing
    phase is diagnosable instead of vanishing into a bare traceback.

    When ``clean`` is set, any prior run directories under ``output_root`` are
    removed first so the batch cannot silently mix stale artifacts.
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

    output_root = output_root.resolve()
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = output_root / run_id
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


_REQUIRED_SCENARIO_ARTIFACTS = ("tree.json", "actual.png")


def verify_captured_artifacts(run_dir: Path) -> dict[str, Any]:
    """Verify that every captured scenario in a run dir has complete artifacts.

    Reads the registry-derived ``batch.json`` and checks, per captured scenario,
    that its manifest declares ``tree.json`` and ``actual.png``, that both exist on
    disk, and that ``actual.png`` is non-empty.  Returns a report with an overall
    ``complete`` flag and a per-scenario breakdown.
    """
    run_dir = run_dir.resolve()
    batch_path = run_dir / "batch.json"
    if not batch_path.is_file():
        raise ValueError(f"Not a capture run directory (missing batch.json): {run_dir}")
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    captured = [str(scenario_id) for scenario_id in batch.get("captured_scenarios", [])]

    scenarios: dict[str, dict[str, Any]] = {}
    complete = True
    for scenario_id in captured:
        scenario_dir = run_dir / scenario_id
        manifest_path = scenario_dir / "manifest.json"
        if not manifest_path.is_file():
            scenarios[scenario_id] = {"complete": False, "missing": ["manifest.json"], "empty": []}
            complete = False
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = {str(file.get("name")) for file in manifest.get("files", [])}
        missing: list[str] = []
        empty: list[str] = []
        for name in _REQUIRED_SCENARIO_ARTIFACTS:
            path = scenario_dir / name
            if name not in declared or not path.is_file():
                missing.append(name)
            elif path.stat().st_size == 0:
                empty.append(name)
        scenario_complete = not missing and not empty
        scenarios[scenario_id] = {"complete": scenario_complete, "missing": missing, "empty": empty}
        if not scenario_complete:
            complete = False

    return {
        "run_id": batch.get("run_id"),
        "complete": complete,
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture all admitted Xenix UI scenarios")
    parser.add_argument("--output", type=Path, required=True, help="Artifact output root")
    parser.add_argument("--scenario", action="append", default=None, help="Capture only this scenario (repeatable)")
    parser.add_argument("--clean", action="store_true", help="Remove prior run directories before capturing")
    parser.add_argument("--verify", type=Path, default=None, help="Verify an existing capture run directory")
    args = parser.parse_args()

    if args.verify is not None:
        report = verify_captured_artifacts(args.verify)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["complete"] else 1

    batch = capture_all_scenarios(args.output.resolve(), args.scenario, clean=args.clean)
    print(json.dumps(batch, ensure_ascii=False, sort_keys=True))
    return 0 if batch["reconciled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
