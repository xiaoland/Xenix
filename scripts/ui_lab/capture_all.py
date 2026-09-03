from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse
import json
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from xenix.config import default_app_home
from xenix.ui.diagnostics import CapturePolicy, capture_ui_artifacts
from xenix.ui.diagnostics.schema import UI_ARTIFACT_SCHEMA_VERSION

from .contracts import ScenarioContext
from .driver import configure_scenario_application, settle_scenario
from .registry import list_scenarios


# The exact run-id format capture_all_scenarios mints, e.g. 20260902T153045123456Z.
_RUN_ID_PATTERN = re.compile(r"\A\d{8}T\d{12}Z\Z")


def _repository_root() -> Path:
    """The source repository root containing this script, if discoverable."""
    current = Path(__file__).resolve().parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return current


def _refuse_dangerous_root(output_root: Path) -> None:
    """Refuse to prune from a root where a mistake is unrecoverable.

    Pruning is bounded to run directories immediately under ``output_root``, but
    the caller must never pass a location whose direct children are not safe to
    enumerate and delete.  This hard-rejects the repository root, the user home,
    the runtime home, the system temp root, and a drive root.
    """
    dangerous = {
        Path.home().resolve(),
        _repository_root().resolve(),
        default_app_home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
        Path(output_root.anchor).resolve(),
    }
    if output_root in dangerous:
        raise ValueError(f"Refusing to prune run directories from {output_root}")


def _is_capture_run_dir(run_dir: Path) -> bool:
    """Whether ``run_dir`` is a Xenix capture run dir this script minted."""
    if _RUN_ID_PATTERN.fullmatch(run_dir.name) is None:
        return False
    batch_path = run_dir / "batch.json"
    if not batch_path.is_file():
        return False
    try:
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(batch, dict) and str(batch.get("run_id")) == run_dir.name


def prune_run_directories(output_root: Path) -> int:
    """Delete only historical Xenix capture run dirs directly under ``output_root``.

    Returns the number of removed run directories.  Never removes ``output_root``
    itself, never recurses, and only touches an immediate child when all of the
    following hold: its name matches the Xenix run-id format, it contains a valid
    ``batch.json``, and that manifest's ``run_id`` equals the directory name.
    """
    output_root = output_root.resolve()
    _refuse_dangerous_root(output_root)
    if not output_root.is_dir():
        return 0
    pruned = 0
    for child in output_root.iterdir():
        if child.is_dir() and _is_capture_run_dir(child):
            shutil.rmtree(child)
            pruned += 1
    return pruned


def capture_all_scenarios(
    output_root: Path,
    scenario_ids: list[str] | None = None,
    *,
    prune_runs: bool = False,
) -> dict[str, Any]:
    """Capture every admitted scenario from the registry into a fresh run dir.

    Returns a batch manifest. A scenario that fails to build, settle, or capture is
    recorded as a failure and still emits a stage-tagged manifest so the failing
    phase is diagnosable instead of vanishing into a bare traceback.

    When ``prune_runs`` is set, only historical Xenix run directories already under
    ``output_root`` are removed first; ``output_root`` itself and any sibling
    content are left intact.
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
    if prune_runs:
        prune_run_directories(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = output_root / run_id
    captured: list[str] = []
    failures: list[dict[str, str]] = []

    for scenario in list_scenarios():
        if scenario.id not in expected:
            continue
        configured = False
        try:
            configure_scenario_application(app, scenario)
            configured = True
            handle = scenario.build(ScenarioContext(app))
        except Exception as exc:
            stage = "build" if configured else "configure"
            failures.append(_failure(scenario.id, stage, exc))
            _write_failure_manifest(run_dir, scenario.id, stage, exc)
            continue
        try:
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
    """Verify that every captured scenario in a run dir has complete artifacts
    and that the batch is reconciled (expected == captured, no failures).

    Reads the registry-derived ``batch.json`` and checks, per captured scenario,
    that its manifest declares ``tree.json`` and ``actual.png``, that both exist on
    disk, and that ``actual.png`` is non-empty.  Also checks that the run's
    ``reconciled`` flag is true and the ``failures`` list is empty.  Returns a
    report with an overall ``complete`` flag and a per-scenario breakdown.
    """
    run_dir = run_dir.resolve()
    batch_path = run_dir / "batch.json"
    if not batch_path.is_file():
        raise ValueError(f"Not a capture run directory (missing batch.json): {run_dir}")
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    captured = [str(scenario_id) for scenario_id in batch.get("captured_scenarios", [])]
    expected = [str(scenario_id) for scenario_id in batch.get("expected_scenarios", [])]
    failures = list(batch.get("failures", []))

    reconciled = batch.get("reconciled", False)
    if not reconciled and not captured and not failures:
        # batch.json may have been written by an older version; validate manually
        reconciled = not failures and set(expected) == set(captured)

    scenarios: dict[str, dict[str, Any]] = {}
    complete = reconciled
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
        "reconciled": reconciled,
        "expected_scenarios": sorted(expected),
        "captured_scenarios": sorted(captured),
        "failures": failures,
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture all admitted Xenix UI scenarios")
    parser.add_argument("--output", type=Path, required=True, help="Artifact output root")
    parser.add_argument("--scenario", action="append", default=None, help="Capture only this scenario (repeatable)")
    parser.add_argument(
        "--prune-runs",
        action="store_true",
        help="Remove only historical Xenix capture run dirs under --output before capturing",
    )
    parser.add_argument("--verify", type=Path, default=None, help="Verify an existing capture run directory")
    args = parser.parse_args()

    if args.verify is not None:
        report = verify_captured_artifacts(args.verify)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["complete"] else 1

    batch = capture_all_scenarios(args.output.resolve(), args.scenario, prune_runs=args.prune_runs)
    print(json.dumps(batch, ensure_ascii=False, sort_keys=True))
    return 0 if batch["reconciled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
