from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QLibraryInfo


def _resolve_lupdate() -> Path:
    command = Path(
        QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath)
    ) / "lupdate.exe"
    if not command.is_file():
        raise SystemExit("lupdate is not available in the active PySide6 installation.")
    return command


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src" / "xenix"
    translations_root = source_root / "translations"
    translations_root.mkdir(parents=True, exist_ok=True)
    source_files = [str(path) for path in sorted(source_root.rglob("*.py"))]

    command = _resolve_lupdate()

    subprocess.run(
        [
            command,
            *source_files,
            "-extensions",
            "py",
            "-ts",
            str(translations_root / "xenix_en_US.ts"),
            str(translations_root / "xenix_zh_CN.ts"),
        ],
        check=True,
        cwd=project_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
