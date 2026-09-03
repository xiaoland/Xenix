from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import traceback
from datetime import UTC, datetime
from multiprocessing import freeze_support
from pathlib import Path
from typing import Sequence

from .runtime_profile import (
    RuntimeProfileContext,
    is_isolated_home_path,
    resolve_runtime_profile,
)
from .single_instance import SingleInstanceGuard


EVIDENCE_DIR_ENV = "XENIX_EVIDENCE_DIR"
DEFAULT_EVIDENCE_DIR = "ui-artifacts"
MAX_ERROR_CHARS = 4_000
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/][^\s\"']+")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xenix")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Initialize the native app and exit after startup validation.",
    )
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Run with a unique fresh temp home; never read, migrate, or write the real user home.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    freeze_support()
    args = build_argument_parser().parse_args(list(argv) if argv is not None else None)
    # Resolve the typed profile, set the home, acquire the home-scoped mutex,
    # and only then import the application.  This guarantees that any future
    # app-level import-time path resolution sees the correct XENIX_APP_HOME
    # and that the home is never reached without the mutex held.
    profile = resolve_runtime_profile(
        isolated=args.isolated,
        smoke_test=args.smoke_test,
    )
    if profile.isolated_home:
        os.environ["XENIX_APP_HOME"] = str(profile.runtime_home)
    _print_run_manifest(profile)

    guard = SingleInstanceGuard(profile.mutex_name())
    try:
        from .app import run

        exit_code = run(smoke_test=args.smoke_test)
    except BaseException:
        if profile.isolated_home:
            exc_type, exc_value, _tb = sys.exc_info()
            _preserve_failure_evidence(profile, exc_type, exc_value)
        raise
    else:
        if profile.isolated_home:
            if exit_code == 0:
                _remove_isolated_home(profile.runtime_home)
            else:
                _preserve_failure_evidence(
                    profile,
                    RuntimeError,
                    RuntimeError(f"run exited with code {exit_code}"),
                )
        return exit_code
    finally:
        guard.close()


def _print_run_manifest(profile: RuntimeProfileContext) -> None:
    print(json.dumps(profile.run_manifest(), ensure_ascii=False, sort_keys=True), file=sys.stderr)


def _remove_isolated_home(runtime_home: Path) -> None:
    # A successful isolated run leaves no fresh home behind. Failure keeps the
    # home for diagnosis and instead publishes bounded evidence outside it.
    #
    # This is a hard safety boundary: refuse to recursively remove anything
    # Xenix did not mint itself (never the user home, a drive root, or an
    # arbitrary directory), and fail loudly instead of silently ignoring errors.
    resolved = runtime_home.resolve()
    if not is_isolated_home_path(resolved):
        raise RuntimeError(
            f"Refusing to remove non-isolated runtime home: {resolved}"
        )
    shutil.rmtree(resolved)


def _preserve_failure_evidence(profile: RuntimeProfileContext, exc_type, exc_value) -> None:
    summary = "".join(traceback.format_exception_only(exc_type, exc_value)).strip()
    root = Path(os.environ.get(EVIDENCE_DIR_ENV, DEFAULT_EVIDENCE_DIR)).resolve()
    destination = root / profile.run_id
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "profile": profile.profile.value,
        "run_id": profile.run_id,
        "runtime_home": str(profile.runtime_home),
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "error": _redact_error(summary),
    }
    (destination / "failure.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _redact_error(value: str) -> str:
    redacted = value.replace(str(Path.home()), "<home>")
    redacted = _WINDOWS_PATH.sub("<path>", redacted)
    return redacted[:MAX_ERROR_CHARS]


if __name__ == "__main__":
    raise SystemExit(main())
