from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--executable",
        default=None,
        help="Path to the packaged executable. Defaults to dist/xenix/xenix.exe.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Maximum time to wait for the packaged smoke test.",
    )
    return parser


def resolve_executable(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).resolve()

    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "dist" / "xenix" / "xenix.exe").resolve()


def main() -> int:
    args = build_argument_parser().parse_args()
    executable = resolve_executable(args.executable)
    if not executable.is_file():
        raise FileNotFoundError(f"Packaged executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="xenix-packaged-smoke-") as runtime_home:
        runtime_root = Path(runtime_home)
        environment = os.environ.copy()
        environment["XENIX_APP_HOME"] = str(runtime_root)

        completed = subprocess.run(
            [str(executable), "--smoke-test"],
            cwd=str(executable.parent),
            env=environment,
            timeout=args.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Packaged smoke test failed with exit code {completed.returncode}.")

        expected_paths = [
            runtime_root / "config",
            runtime_root / "logs",
            runtime_root / "cache",
            runtime_root / "state",
            runtime_root / "temp",
            runtime_root / "artifacts",
            runtime_root / "state" / "xenix.db",
            runtime_root / "logs" / "xenix.log",
        ]
        missing = [path for path in expected_paths if not path.exists()]
        if missing:
            joined = ", ".join(str(path) for path in missing)
            raise RuntimeError(f"Packaged smoke test did not create expected runtime artifacts: {joined}")

    print(f"Packaged smoke test passed for {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
