from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo


def _resolve_lrelease() -> Path:
    command = Path(
        QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath)
    ) / "lrelease.exe"
    if not command.is_file():
        raise SystemExit("lrelease is not available in the active PySide6 installation.")
    return command


def _supported_translation_names(project_root: Path) -> frozenset[str]:
    source_root = project_root / "src"
    sys.path.insert(0, str(source_root))
    try:
        from xenix.i18n import SUPPORTED_LOCALES, TRANSLATION_BASENAME
    finally:
        sys.path.remove(str(source_root))
    return frozenset(
        f"{TRANSLATION_BASENAME}_{locale_code}.ts"
        for locale_code in SUPPORTED_LOCALES
    )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    translations_root = project_root / "src" / "xenix" / "translations"
    ts_paths = sorted(translations_root.glob("*.ts"))
    if not ts_paths:
        raise SystemExit("No translation source files were found.")
    found_names = {path.name for path in ts_paths}
    missing_names = sorted(_supported_translation_names(project_root) - found_names)
    if missing_names:
        raise SystemExit(
            "Translation sources are missing for supported locales: "
            + ", ".join(missing_names)
        )

    command = _resolve_lrelease()

    for ts_path in ts_paths:
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
        if not qm_path.is_file() or qm_path.stat().st_size == 0:
            raise SystemExit(
                f"Translation compiler did not produce a non-empty output: {qm_path}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
