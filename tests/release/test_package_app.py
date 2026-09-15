from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from tests.support.paths import project_script


def _load_package_app():
    path = project_script("package_app.py")
    spec = importlib.util.spec_from_file_location("xenix_package_app_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package_app = _load_package_app()


def test_windows_pyinstaller_does_not_inherit_ambient_binary_paths(tmp_path: Path) -> None:
    python_prefix = tmp_path / "venv"
    python_base_prefix = tmp_path / "python"
    windows_root = tmp_path / "Windows"
    ambient_binary_path = tmp_path / "ambient-native-runtime"
    for path in (
        python_prefix / "Scripts",
        python_prefix,
        python_base_prefix,
        python_base_prefix / "DLLs",
        windows_root / "System32",
        windows_root,
        ambient_binary_path,
    ):
        path.mkdir(parents=True, exist_ok=True)

    environment = package_app._pyinstaller_environment(
        {
            "PATH": str(ambient_binary_path),
            "SystemRoot": str(windows_root),
            "SOURCE_DATE_EPOCH": "1",
        },
        python_executable=python_prefix / "Scripts" / "python.exe",
        python_prefix=python_prefix,
        python_base_prefix=python_base_prefix,
        platform="win32",
    )

    resolved_paths = [Path(value) for value in environment["PATH"].split(os.pathsep)]
    assert ambient_binary_path.resolve() not in resolved_paths
    assert resolved_paths == [
        (python_prefix / "Scripts").resolve(),
        python_prefix.resolve(),
        python_base_prefix.resolve(),
        (python_base_prefix / "DLLs").resolve(),
        (windows_root / "System32").resolve(),
        windows_root.resolve(),
    ]
    assert environment["SOURCE_DATE_EPOCH"] == "1"
