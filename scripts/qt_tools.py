"""Locate Qt Linguist command-line tools shipped with the active PySide6 wheel."""

from __future__ import annotations

import sys
from pathlib import Path


def resolve_qt_tool(name: str) -> Path:
    """Return the platform executable for a PySide6-bundled Qt tool such as ``lrelease``.

    Windows wheels place tools under Qt's LibraryExecutablesPath with an ``.exe``
    suffix; macOS and Linux wheels place them beside the PySide6 package.
    """
    import PySide6
    from PySide6.QtCore import QLibraryInfo

    executable = f"{name}.exe" if sys.platform == "win32" else name
    candidates = (
        Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath)) / executable,
        Path(PySide6.__file__).resolve().parent / executable,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"{name} is not available in the active PySide6 installation.")
