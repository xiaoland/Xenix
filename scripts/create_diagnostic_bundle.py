from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import sys
import zipfile
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


def _project_src_path() -> Path:
    return Path(__file__).resolve().parents[1] / "src"


if str(_project_src_path()) not in sys.path:
    sys.path.insert(0, str(_project_src_path()))

from xenix.config import AppPaths, ensure_app_dirs, get_app_paths  # noqa: E402
from xenix.logging import LOG_FILE_NAME  # noqa: E402
from xenix.observability import load_or_create_install_id  # noqa: E402
from xenix.services.storage.layout import (  # noqa: E402
    database_path,
    knowledge_import_task_root,
    ml_task_parent_root,
)

MAX_LOG_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_LOG_BYTES = 32 * 1024 * 1024


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="create_diagnostic_bundle")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output zip path. Defaults to temp/xenix-diagnostic-<timestamp>.zip.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(list(argv) if argv is not None else None)
    paths = ensure_app_dirs(get_app_paths())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = args.output or (paths.temp / f"xenix-diagnostic-{stamp}.zip")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "install_id": load_or_create_install_id(paths),
        "runtime_home_class": "custom" if os.getenv("XENIX_APP_HOME") else "default",
        "sqlite": _sqlite_summary(database_path(paths)),
    }

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        _write_if_exists(bundle, paths.config / "telemetry.json", "config/telemetry.json")
        metadata["logs"] = _write_logs(bundle, paths)
        bundle.writestr("metadata.json", json.dumps(metadata, indent=2, ensure_ascii=True))

    print(output_path)
    return 0


def _write_if_exists(bundle: zipfile.ZipFile, path: Path, archive_name: str) -> None:
    if path.exists() and path.is_file():
        bundle.write(path, archive_name)


def _log_paths(paths: AppPaths) -> Iterator[Path]:
    yield paths.logs / LOG_FILE_NAME
    prefix = f"{LOG_FILE_NAME}."
    rotated_logs = []
    for path in paths.logs.glob(f"{prefix}*"):
        sequence = path.name.removeprefix(prefix)
        if sequence.isascii() and sequence.isdecimal():
            rotated_logs.append((int(sequence), path))
    yield from (path for _, path in sorted(rotated_logs))
    yield from sorted(ml_task_parent_root(paths).glob("*/logs.jsonl"))
    yield from sorted(knowledge_import_task_root(paths, 1).parent.glob("*/logs.jsonl"))


def _read_log(path: Path, remaining_bytes: int) -> bytes | str:
    limit = min(MAX_LOG_FILE_BYTES, remaining_bytes)
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            return "not_a_file"
        if info.st_size > MAX_LOG_FILE_BYTES:
            return "file_limit"
        if info.st_size > remaining_bytes:
            return "total_limit"
        with path.open("rb") as source:
            # The log can grow after stat while Xenix is running.
            content = source.read(limit + 1)
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    if len(content) > limit:
        return "file_limit" if limit == MAX_LOG_FILE_BYTES else "total_limit"
    return content


def _write_logs(bundle: zipfile.ZipFile, paths: AppPaths) -> dict[str, Any]:
    total_bytes = 0
    omitted = []
    for path in _log_paths(paths):
        name = path.relative_to(paths.home).as_posix()
        result = _read_log(path, MAX_TOTAL_LOG_BYTES - total_bytes)
        if isinstance(result, str):
            omitted.append({"path": name, "reason": result})
        else:
            bundle.writestr(name, result)
            total_bytes += len(result)
    return {
        "max_file_bytes": MAX_LOG_FILE_BYTES,
        "max_total_bytes": MAX_TOTAL_LOG_BYTES,
        "included_bytes": total_bytes,
        "omitted": omitted,
    }


def _sqlite_summary(path: Path) -> dict[str, Any]:
    exists = None
    try:
        path.stat()
        exists = True
        with closing(sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True, timeout=1.0)) as connection:
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            counts: dict[str, int] = {}
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
    except FileNotFoundError:
        return {"exists": False}
    except (OSError, sqlite3.Error) as error:
        return {
            "exists": exists,
            "status": "unavailable",
            "error": {
                "category": getattr(error, "sqlite_errorname", type(error).__name__),
                "message": "SQLite database summary could not be read.",
            },
        }
    return {
        "exists": True,
        "user_version": user_version,
        "table_counts": counts,
    }


if __name__ == "__main__":
    raise SystemExit(main())
