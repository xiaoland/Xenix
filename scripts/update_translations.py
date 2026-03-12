from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src" / "xenix"
    translations_root = source_root / "translations"
    translations_root.mkdir(parents=True, exist_ok=True)
    source_files = [str(path) for path in sorted(source_root.rglob("*.py"))]

    command = shutil.which("pyside6-lupdate")
    if command is None:
        raise SystemExit("pyside6-lupdate is not available in the active environment.")

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
