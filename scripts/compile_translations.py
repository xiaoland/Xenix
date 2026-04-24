from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _resolve_lrelease(project_root: Path) -> str | None:
    command = shutil.which("pyside6-lrelease")
    if command is not None:
        return command

    candidates = (
        project_root / ".venv" / "Scripts" / "pyside6-lrelease.exe",
        project_root / ".venv" / "Lib" / "site-packages" / "PySide6" / "lrelease.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    translations_root = project_root / "src" / "xenix" / "translations"

    command = _resolve_lrelease(project_root)
    if command is None:
        raise SystemExit("pyside6-lrelease is not available in the active environment.")

    for ts_path in sorted(translations_root.glob("*.ts")):
        qm_path = ts_path.with_suffix(".qm")
        subprocess.run(
            [
                command,
                str(ts_path),
                "-qm",
                str(qm_path),
            ],
            check=True,
            cwd=project_root,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
