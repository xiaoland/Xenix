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

    if not _has_basetemp_argument(args):
        basetemp = _default_basetemp()
        basetemp.parent.mkdir(parents=True, exist_ok=True)
        args.append(f"--basetemp={basetemp}")

    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
