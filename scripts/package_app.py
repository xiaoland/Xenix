from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(project_root / "scripts" / "compile_translations.py")],
        check=True,
        cwd=project_root,
    )
    pyinstaller_run(
        [
            "--clean",
            "--noconfirm",
            str(project_root / "xenix.spec"),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
