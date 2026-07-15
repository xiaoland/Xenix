from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


def _generate_agent_skill_catalog() -> None:
    project_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(project_root / "scripts" / "agent_skills.py"), "generate"],
        check=True,
        cwd=project_root,
    )
    subprocess.run(
        [sys.executable, str(project_root / "scripts" / "agent_skills.py"), "check"],
        check=True,
        cwd=project_root,
    )


def _has_basetemp_argument(args: list[str]) -> bool:
    for index, arg in enumerate(args):
        if arg == "--basetemp":
            return True
        if arg.startswith("--basetemp="):
            return True
        if index > 0 and args[index - 1] == "--basetemp":
            return True
    return False


def _default_basetemp() -> Path:
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    return Path(tempfile.gettempdir()) / "xenix-native-pytest-runs" / run_id


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    _generate_agent_skill_catalog()

    # Qt owns native process-global state. The workbench suite deliberately
    # creates and tears down several QApplication/splash combinations, while
    # the remainder exercises multiprocessing and native ML libraries. Run a
    # default repository verification in two clean processes so PDM's public
    # test command remains deterministic on Windows. Targeted pytest arguments
    # retain their normal one-process behavior.
    if not args:
        project_root = Path(__file__).resolve().parents[1]
        basetemp = _default_basetemp()
        basetemp.mkdir(parents=True, exist_ok=True)
        commands = [
            [
                sys.executable,
                "-m",
                "pytest",
                "--ignore",
                "tests/test_main.py",
                f"--basetemp={basetemp / 'non-ui'}",
            ],
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_main.py",
                f"--basetemp={basetemp / 'ui'}",
            ],
        ]
        for command in commands:
            completed = subprocess.run(command, cwd=project_root, check=False)
            if completed.returncode:
                return completed.returncode
        return 0

    if not _has_basetemp_argument(args):
        basetemp = _default_basetemp()
        basetemp.parent.mkdir(parents=True, exist_ok=True)
        args.append(f"--basetemp={basetemp}")

    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
