from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_ROOT.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_EXE = PROJECT_ROOT / "dist" / "xenix" / "xenix.exe"
ISO_FMT = "%Y%m%d-%H%M%S"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_log_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_subprocess(
    args: list[str],
    *,
    cwd: Path = PROJECT_ROOT,
    env: dict[str, str] | None = None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    started_at = utc_now()
    started = time.perf_counter()
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "args": args,
        "cwd": str(cwd),
        "started_at": started_at.isoformat(),
        "returncode": completed.returncode,
        "elapsed_ms": round(elapsed_ms, 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def source_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    pythonpath = str(SRC_ROOT)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = pythonpath if not existing else os.pathsep.join([pythonpath, existing])
    if extra:
        env.update(extra)
    return env


def collect_bundle_inventory(exe: Path, output_root: Path) -> dict[str, Any]:
    dist_root = exe.parent
    files = [path for path in dist_root.rglob("*") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    extension_counts = Counter(path.suffix.lower() or "<no extension>" for path in files)
    top_files = sorted(files, key=lambda path: path.stat().st_size, reverse=True)[:40]
    payload = {
        "dist_root": str(dist_root),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 2),
        "extension_counts": [
            {"extension": extension, "count": count}
            for extension, count in extension_counts.most_common(40)
        ],
        "top_files": [
            {
                "relative_path": str(path.relative_to(dist_root)),
                "bytes": path.stat().st_size,
                "mb": round(path.stat().st_size / 1024 / 1024, 2),
            }
            for path in top_files
        ],
    }
    write_json(output_root / "bundle_inventory.json", payload)
    return payload


def collect_source_import_sequence(output_root: Path) -> dict[str, Any]:
    code = r"""
from __future__ import annotations
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
items = [
    ("xenix.main", "main"),
    ("xenix.app", "app"),
    ("xenix.services.agent", "agent exports"),
    ("xenix.services.artifact_service", "artifact service"),
    ("xenix.services.data_cleaning", "data cleaning"),
    ("xenix.services.data_transform", "data transform"),
    ("xenix.services.dataset_service", "dataset service"),
    ("xenix.services.llm", "llm exports"),
    ("xenix.services.ml.worker_settings", "ml worker settings"),
    ("xenix.services.ml_service", "ml service"),
    ("xenix.services.ml_task_service", "ml task service"),
    ("xenix.services.storage", "storage exports"),
    ("xenix.services.storage.layout", "storage layout"),
    ("xenix.ui.main_window", "main window"),
]
start = time.perf_counter()
for module, label in items:
    before = time.perf_counter()
    importlib.import_module(module)
    after = time.perf_counter()
    print(f"{module}\t{label}\t{after - before:.6f}\t{after - start:.6f}")
"""
    result = run_subprocess(
        [sys.executable, "-c", code],
        env=source_env(),
        timeout_seconds=180.0,
    )
    write_text(output_root / "source_import_sequence.stdout.txt", result["stdout"])
    write_text(output_root / "source_import_sequence.stderr.txt", result["stderr"])
    rows: list[dict[str, Any]] = []
    for line in result["stdout"].splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        rows.append(
            {
                "module": parts[0],
                "label": parts[1],
                "elapsed_s": float(parts[2]),
                "cumulative_s": float(parts[3]),
            }
        )
    payload = {key: value for key, value in result.items() if key not in {"stdout", "stderr"}}
    payload["rows"] = rows
    write_json(output_root / "source_import_sequence.json", payload)
    return payload


def collect_isolated_imports(output_root: Path, *, repeat: int) -> dict[str, Any]:
    modules = [
        "xenix.main",
        "xenix.app",
        "xenix.services.agent",
        "xenix.services.agent.tools",
        "xenix.services.ml.registry",
        "xenix.services.ml.models.classification",
        "xenix.services.ml.models.regression",
        "xenix.ui.main_window",
    ]
    rows: list[dict[str, Any]] = []
    code_template = r"""
from __future__ import annotations
import importlib
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
module = {module_name!r}
started = time.perf_counter()
importlib.import_module(module)
elapsed = time.perf_counter() - started
print(module + "\t" + format(elapsed, ".6f"))
"""
    for module in modules:
        for iteration in range(1, repeat + 1):
            result = run_subprocess(
                [sys.executable, "-c", code_template.format(module_name=module)],
                env=source_env(),
                timeout_seconds=180.0,
            )
            elapsed_s = None
            for line in result["stdout"].splitlines():
                parts = line.split("\t")
                if len(parts) == 2 and parts[0] == module:
                    elapsed_s = float(parts[1])
            rows.append(
                {
                    "module": module,
                    "iteration": iteration,
                    "returncode": result["returncode"],
                    "elapsed_s": elapsed_s,
                    "process_elapsed_ms": result["elapsed_ms"],
                    "stderr_tail": result["stderr"][-2000:],
                }
            )
    payload = {"repeat": repeat, "rows": rows}
    write_json(output_root / "source_isolated_imports.json", payload)
    return payload


def collect_importtime(output_root: Path, modules: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {"modules": []}
    for module in modules:
        code = (
            "from pathlib import Path; import sys; "
            "sys.path.insert(0, str(Path('src').resolve())); "
            f"import {module}"
        )
        result = run_subprocess(
            [sys.executable, "-X", "importtime", "-c", code],
            env=source_env(),
            timeout_seconds=180.0,
        )
        safe_name = module.replace(".", "_")
        write_text(output_root / f"importtime_{safe_name}.stderr.txt", result["stderr"])
        rows = parse_importtime_stderr(result["stderr"])
        top_rows = sorted(rows, key=lambda row: row["cumulative_us"], reverse=True)[:60]
        payload["modules"].append(
            {
                "module": module,
                "returncode": result["returncode"],
                "elapsed_ms": result["elapsed_ms"],
                "top_cumulative": top_rows,
            }
        )
    write_json(output_root / "source_importtime_summary.json", payload)
    return payload


def parse_importtime_stderr(stderr: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stderr.splitlines():
        if not line.startswith("import time:"):
            continue
        fields = line.removeprefix("import time:").split("|")
        if len(fields) != 3:
            continue
        try:
            self_us = int(fields[0].strip())
            cumulative_us = int(fields[1].strip())
        except ValueError:
            continue
        rows.append(
            {
                "self_us": self_us,
                "cumulative_us": cumulative_us,
                "module": fields[2].strip(),
            }
        )
    return rows


def collect_qt_plugin_probe(output_root: Path) -> dict[str, Any]:
    code = r"""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
started = time.perf_counter()
from PySide6.QtWidgets import QApplication
after_import = time.perf_counter()
app = QApplication([])
after_app = time.perf_counter()
print(f"pyside_import_s={after_import - started:.6f}")
print(f"qapplication_create_s={after_app - after_import:.6f}")
"""
    result = run_subprocess(
        [sys.executable, "-c", code],
        env=source_env({"QT_DEBUG_PLUGINS": "1"}),
        timeout_seconds=120.0,
    )
    write_text(output_root / "qt_plugin_probe.stdout.txt", result["stdout"])
    write_text(output_root / "qt_plugin_probe.stderr.txt", result["stderr"])
    payload = {key: value for key, value in result.items() if key not in {"stdout", "stderr"}}
    payload["stderr_line_count"] = len(result["stderr"].splitlines())
    payload["loaded_library_lines"] = [
        line for line in result["stderr"].splitlines() if "loaded library" in line.lower()
    ][-40:]
    write_json(output_root / "qt_plugin_probe.json", payload)
    return payload


def collect_packaged_smoke(
    output_root: Path,
    *,
    exe: Path,
    repeat: int,
    timeout_seconds: float,
    env_extra: dict[str, str] | None = None,
    label: str = "packaged_smoke",
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for iteration in range(1, repeat + 1):
        runtime_home = output_root / f"{label}_home_{iteration}"
        runtime_home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["XENIX_APP_HOME"] = str(runtime_home)
        env["XENIX_STARTUP_TIMING"] = "1"
        if env_extra:
            env.update(env_extra)
        started_at = utc_now()
        started = time.perf_counter()
        process = subprocess.Popen(
            [str(exe), "--smoke-test"],
            cwd=str(exe.parent),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
            timed_out = True
        ended_at = utc_now()
        elapsed_ms = (time.perf_counter() - started) * 1000
        run_dir = output_root / f"{label}_run_{iteration}"
        write_text(run_dir / "stdout.txt", stdout or "")
        write_text(run_dir / "stderr.txt", stderr or "")
        timing_events = parse_startup_timing(stderr or "")
        log_path = runtime_home / "logs" / "xenix.log"
        log_lines = read_json_log_lines(log_path)
        log_deltas = compute_log_deltas(started_at, log_lines)
        runs.append(
            {
                "iteration": iteration,
                "returncode": process.returncode,
                "timed_out": timed_out,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "elapsed_ms": round(elapsed_ms, 3),
                "runtime_home": str(runtime_home),
                "stdout_bytes": len(stdout or ""),
                "stderr_bytes": len(stderr or ""),
                "startup_timing": timing_events,
                "log_path": str(log_path),
                "log_exists": log_path.exists(),
                "log_line_count": len(log_lines),
                "log_deltas": log_deltas,
            }
        )
    payload = {"label": label, "exe": str(exe), "repeat": repeat, "runs": runs}
    write_json(output_root / f"{label}.json", payload)
    return payload


def parse_startup_timing(stderr: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stderr.splitlines():
        if not line.startswith("XENIX_STARTUP_TIMING\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        event: dict[str, Any] = {"event": parts[1]}
        for field in parts[2:]:
            if "=" not in field:
                continue
            key, raw_value = field.split("=", 1)
            try:
                event[key] = float(raw_value)
            except ValueError:
                event[key] = raw_value
        events.append(event)
    return events


def read_json_log_lines(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def compute_log_deltas(started_at: datetime, log_lines: list[dict[str, Any]]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for row in log_lines:
        timestamp = parse_log_timestamp(str(row.get("timestamp") or ""))
        if timestamp is None:
            continue
        event = str(row.get("event") or row.get("event_name") or "")
        events.append(
            {
                "event": event,
                "timestamp": timestamp.isoformat(),
                "delta_from_process_start_ms": round((timestamp - started_at).total_seconds() * 1000, 3),
            }
        )
    first = events[0] if events else None
    by_event = {event["event"]: event for event in events}
    return {
        "first_event": first,
        "events": events,
        "observability_delta_ms": by_event.get("Observability initialized", {}).get("delta_from_process_start_ms"),
        "shell_started_delta_ms": by_event.get("Xenix native shell started", {}).get("delta_from_process_start_ms"),
        "smoke_completed_delta_ms": by_event.get("Xenix smoke test completed", {}).get("delta_from_process_start_ms"),
    }


def copy_dist_for_scan_probe(exe: Path, output_root: Path) -> Path:
    source_root = exe.parent
    target_root = output_root / "copied_dist" / source_root.name
    if target_root.exists():
        shutil.rmtree(target_root)
    started = time.perf_counter()
    shutil.copytree(source_root, target_root)
    elapsed_ms = (time.perf_counter() - started) * 1000
    write_json(
        output_root / "copy_dist.json",
        {
            "source_root": str(source_root),
            "target_root": str(target_root),
            "elapsed_ms": round(elapsed_ms, 3),
        },
    )
    return target_root / exe.name


def write_report(output_root: Path, results: dict[str, Any]) -> None:
    lines = [
        "# Startup Probe Report",
        "",
        f"- Generated: {utc_now().isoformat()}",
        f"- Project root: `{PROJECT_ROOT}`",
        f"- Output root: `{output_root}`",
        "",
        "## Bundle",
    ]
    bundle = results.get("bundle_inventory") or {}
    lines.append(f"- Files: {bundle.get('file_count')}")
    lines.append(f"- Size: {bundle.get('total_mb')} MB")
    top = bundle.get("top_files") or []
    if top:
        lines.append("- Largest files:")
        for item in top[:10]:
            lines.append(f"  - {item['mb']} MB `{item['relative_path']}`")

    lines.extend(["", "## Source Import Sequence"])
    sequence = results.get("source_import_sequence") or {}
    for row in sequence.get("rows", []):
        lines.append(
            f"- `{row['module']}`: {row['elapsed_s']:.3f}s, cumulative {row['cumulative_s']:.3f}s"
        )

    lines.extend(["", "## Packaged Smoke"])
    for key in ("packaged_smoke", "packaged_smoke_qt_debug", "packaged_smoke_profile_imports", "copied_dist_smoke"):
        payload = results.get(key)
        if not payload:
            continue
        lines.append(f"- `{key}`:")
        for run in payload.get("runs", []):
            deltas = run.get("log_deltas") or {}
            lines.append(
                "  - "
                f"run {run['iteration']}: exit {run['returncode']}, "
                f"elapsed {run['elapsed_ms']:.0f}ms, "
                f"first_log {((deltas.get('first_event') or {}).get('delta_from_process_start_ms'))}ms, "
                f"shell_started {deltas.get('shell_started_delta_ms')}ms, "
                f"smoke_done {deltas.get('smoke_completed_delta_ms')}ms, "
                f"stderr {run['stderr_bytes']} bytes"
            )
            timing_events = run.get("startup_timing") or []
            if timing_events:
                interesting = [
                    event
                    for event in timing_events
                    if event.get("event")
                    in {
                        "run_dev.import_xenix_main",
                        "run_packaged.import_xenix_main",
                        "create_application",
                        "splash.show",
                        "runtime_import.module",
                        "runtime_import.total",
                        "load_runtime_imports",
                        "storage.bootstrap",
                        "services.construct",
                        "main_window.construct",
                        "build_main_window.total",
                        "run_dev.application_main",
                        "run_packaged.application_main",
                    }
                ]
                for event in interesting[:20]:
                    label = event.get("event")
                    elapsed = event.get("elapsed_ms")
                    module = event.get("module")
                    suffix = f", module `{module}`" if module else ""
                    lines.append(f"    - {label}: {elapsed}ms{suffix}")

    write_text(output_root / "report.md", "\n".join(lines) + "\n")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--isolated-repeat", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--copy-dist", action="store_true")
    parser.add_argument("--skip-source", action="store_true")
    parser.add_argument("--skip-packaged", action="store_true")
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    timestamp = utc_now().strftime(ISO_FMT)
    output_root = args.output_root or TASK_ROOT / "artifacts" / timestamp
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    exe = args.exe.resolve()
    results: dict[str, Any] = {
        "output_root": str(output_root),
        "exe": str(exe),
        "created_at": utc_now().isoformat(),
    }

    if exe.exists():
        results["bundle_inventory"] = collect_bundle_inventory(exe, output_root)

    if not args.skip_source:
        results["source_import_sequence"] = collect_source_import_sequence(output_root)
        results["source_isolated_imports"] = collect_isolated_imports(
            output_root,
            repeat=args.isolated_repeat,
        )
        results["source_importtime_summary"] = collect_importtime(
            output_root,
            ["xenix.main", "xenix.services.agent", "xenix.services.ml.registry"],
        )
        results["qt_plugin_probe"] = collect_qt_plugin_probe(output_root)

    if not args.skip_packaged:
        if not exe.is_file():
            raise FileNotFoundError(exe)
        results["packaged_smoke"] = collect_packaged_smoke(
            output_root,
            exe=exe,
            repeat=args.repeat,
            timeout_seconds=args.timeout_seconds,
            label="packaged_smoke",
        )
        results["packaged_smoke_qt_debug"] = collect_packaged_smoke(
            output_root,
            exe=exe,
            repeat=1,
            timeout_seconds=args.timeout_seconds,
            env_extra={"QT_DEBUG_PLUGINS": "1"},
            label="packaged_smoke_qt_debug",
        )
        results["packaged_smoke_profile_imports"] = collect_packaged_smoke(
            output_root,
            exe=exe,
            repeat=1,
            timeout_seconds=args.timeout_seconds,
            env_extra={"PYTHONPROFILEIMPORTTIME": "1"},
            label="packaged_smoke_profile_imports",
        )
        if args.copy_dist:
            copied_exe = copy_dist_for_scan_probe(exe, output_root)
            results["copied_dist_smoke"] = collect_packaged_smoke(
                output_root,
                exe=copied_exe,
                repeat=1,
                timeout_seconds=args.timeout_seconds,
                label="copied_dist_smoke",
            )

    write_json(output_root / "results.json", results)
    write_report(output_root, results)
    print(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
