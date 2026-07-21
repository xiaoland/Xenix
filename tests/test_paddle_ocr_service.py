from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.paddle_ocr_service import (
    PADDLE_OCR_VERSION,
    PADDLE_VERSION,
    PYTHON_VERSION,
    PaddleOcrDeploymentService,
    _safe_extract_zip,
)


def test_runtime_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    with ZipFile(archive, "w") as package:
        package.writestr("../escape.txt", "bad")

    with pytest.raises(ValidationError, match="unsafe path"):
        _safe_extract_zip(archive, tmp_path / "runtime")


def test_enable_site_packages_keeps_embedded_runtime_isolated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "home"))
    deployment = PaddleOcrDeploymentService(ensure_app_dirs(get_app_paths()))
    deployment._runtime.mkdir(parents=True)  # noqa: SLF001 - isolated runtime fixture
    pth = deployment._runtime / "python313._pth"  # noqa: SLF001
    pth.write_text("python313.zip\n.\n#import site\n", encoding="utf-8")

    deployment._enable_site_packages()  # noqa: SLF001 - deployment unit boundary

    lines = pth.read_text(encoding="utf-8").splitlines()
    assert "Lib/site-packages" in lines
    assert "import site" in lines
    assert "#import site" not in lines


def test_one_click_install_pins_runtime_and_warms_local_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "home"))
    deployment = PaddleOcrDeploymentService(ensure_app_dirs(get_app_paths()))
    phases: list[str] = []
    calls: list[tuple[str, int]] = []
    deployment._runtime.mkdir(parents=True)  # noqa: SLF001
    (deployment._runtime / "python.exe").write_bytes(b"python")  # noqa: SLF001
    (deployment._runtime / "python313._pth").write_text("python313.zip\n#import site\n", encoding="utf-8")  # noqa: SLF001

    archive = tmp_path / "runtime.zip"
    with ZipFile(archive, "w") as package:
        package.writestr("python.exe", b"python")
        package.writestr("python313._pth", "python313.zip\n#import site\n")
    pip_wheel = tmp_path / "pip.whl"
    pip_wheel.write_bytes(b"pip")
    downloads = iter((archive, pip_wheel))
    monkeypatch.setattr(deployment, "_download_verified", lambda *_args: next(downloads))
    monkeypatch.setattr(
        "xenix.services.paddle_ocr_service.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        deployment,
        "_run_worker",
        lambda command, *, timeout, arguments=None: calls.append((command, timeout)) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        "xenix.services.paddle_ocr_service.package_root",
        lambda: Path(__file__).resolve().parents[1] / "src" / "xenix",
    )
    monkeypatch.setattr(deployment, "status", lambda: SimpleNamespace(installed=True, models_ready=True))

    status = deployment.install(phases.append)

    assert status.installed and status.models_ready
    assert phases == ["downloading_python", "installing_pip", "installing_worker", "downloading_models", "ready"]
    assert [call[0] for call in calls] == ["health", "warmup"]
    manifest = deployment._manifest_path.read_text(encoding="utf-8")  # noqa: SLF001
    assert PYTHON_VERSION in manifest
    assert PADDLE_VERSION in manifest
    assert PADDLE_OCR_VERSION in manifest
