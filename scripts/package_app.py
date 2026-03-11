from __future__ import annotations

from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
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
