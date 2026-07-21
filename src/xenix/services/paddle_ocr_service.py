from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from zipfile import ZipFile

from ..config import AppPaths, package_root
from ..exceptions import ValidationError

PYTHON_VERSION = "3.13.13"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_EMBED_SHA256 = "8766a8775746235e23cf5aee5027ab1060bb981d93110577adcf3508aa0cbd55"
PIP_VERSION = "26.1.2"
PIP_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/5d/95/"
    "6b5cb3461ea5673ba0995989746db58eb18b91b54dbf331e72f569540946/"
    f"pip-{PIP_VERSION}-py3-none-any.whl"
)
PIP_WHEEL_SHA256 = "382ff9f685ee3bc25864f820aa50505825f10f5458ffff07e30a6d96e5715cab"
PADDLE_VERSION = "3.3.1"
PADDLE_OCR_VERSION = "3.7.0"
SIDECAR_PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class PaddleOcrStatus:
    installed: bool
    models_ready: bool
    runtime_path: str | None
    detail: str | None = None


class PaddleOcrDeploymentService:
    """Install and health-check an isolated local PaddleOCR runtime."""

    def __init__(self, paths: AppPaths) -> None:
        self._root = paths.cache / "knowledge-ocr"
        self._runtime = self._root / f"python-{PYTHON_VERSION}"
        self._downloads = self._root / "downloads"
        self._manifest_path = self._root / "active.json"

    @property
    def python_path(self) -> Path:
        return self._runtime / "python.exe"

    @property
    def worker_path(self) -> Path:
        return self._runtime / "paddle_worker.py"

    def status(self) -> PaddleOcrStatus:
        if not self.python_path.is_file() or not self.worker_path.is_file():
            return PaddleOcrStatus(False, False, None)
        probe = self._run_worker("health", timeout=60)
        if probe.returncode != 0:
            return PaddleOcrStatus(False, False, str(self._runtime), "health_check_failed")
        models_ready = False
        if self._manifest_path.is_file():
            try:
                models_ready = bool(json.loads(self._manifest_path.read_text(encoding="utf-8")).get("models_ready"))
            except (OSError, json.JSONDecodeError):
                models_ready = False
        return PaddleOcrStatus(True, models_ready, str(self._runtime))

    def install(self, progress: Callable[[str], None] | None = None) -> PaddleOcrStatus:
        report = progress or (lambda _phase: None)
        self._root.mkdir(parents=True, exist_ok=True)
        self._downloads.mkdir(parents=True, exist_ok=True)
        report("downloading_python")
        python_zip = self._download_verified(
            PYTHON_EMBED_URL,
            self._downloads / Path(PYTHON_EMBED_URL).name,
            PYTHON_EMBED_SHA256,
        )
        if self._runtime.exists():
            shutil.rmtree(self._runtime)
        self._runtime.mkdir(parents=True)
        _safe_extract_zip(python_zip, self._runtime)
        self._enable_site_packages()

        report("installing_pip")
        pip_wheel = self._download_verified(
            PIP_WHEEL_URL,
            self._downloads / Path(PIP_WHEEL_URL).name,
            PIP_WHEEL_SHA256,
        )
        site_packages = self._runtime / "Lib" / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.python_path),
            f"{pip_wheel}/pip",
            "install",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            "--target",
            str(site_packages),
            f"paddlepaddle=={PADDLE_VERSION}",
            f"paddleocr=={PADDLE_OCR_VERSION}",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
        if completed.returncode != 0:
            raise ValidationError("PaddleOCR local runtime installation failed.")

        report("installing_worker")
        worker_source = package_root() / "resources" / "knowledge_ocr" / "paddle_worker.py"
        if not worker_source.is_file():
            raise ValidationError("PaddleOCR worker resource is missing.")
        shutil.copyfile(worker_source, self.worker_path)
        health = self._run_worker("health", timeout=120)
        if health.returncode != 0:
            raise ValidationError("PaddleOCR local runtime health check failed.")

        report("downloading_models")
        warmup = self._run_worker("warmup", timeout=1800)
        if warmup.returncode != 0:
            raise ValidationError("PaddleOCR local models could not be prepared.")
        self._manifest_path.write_text(
            json.dumps(
                {
                    "protocol": SIDECAR_PROTOCOL_VERSION,
                    "python": PYTHON_VERSION,
                    "paddle": PADDLE_VERSION,
                    "paddleocr": PADDLE_OCR_VERSION,
                    "models_ready": True,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        report("ready")
        return self.status()

    def _run_worker(self, command: str, *, timeout: int, arguments: list[str] | None = None):
        environment = os.environ.copy()
        environment["HOME"] = str(self._root)
        environment["USERPROFILE"] = str(self._root)
        environment["PADDLEX_HOME"] = str(self._root / "models")
        environment["PADDLEOCR_HOME"] = str(self._root / "models")
        return subprocess.run(
            [str(self.python_path), str(self.worker_path), command, *(arguments or ())],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )

    def _enable_site_packages(self) -> None:
        pth = next(self._runtime.glob("python*._pth"), None)
        if pth is None:
            raise ValidationError("Embedded Python path configuration is missing.")
        lines = [line for line in pth.read_text(encoding="utf-8").splitlines() if line.strip() != "#import site"]
        lines.extend(["Lib/site-packages", "import site"])
        pth.write_text("\n".join(dict.fromkeys(lines)) + "\n", encoding="utf-8")

    def _download_verified(self, url: str, target: Path, expected_sha256: str) -> Path:
        if target.is_file() and _sha256(target) == expected_sha256:
            return target
        partial = target.with_suffix(target.suffix + ".part")
        partial.unlink(missing_ok=True)
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if _sha256(partial) != expected_sha256:
            partial.unlink(missing_ok=True)
            raise ValidationError("Downloaded PaddleOCR runtime component failed integrity verification.")
        os.replace(partial, target)
        return target


class PaddleOcrService:
    def __init__(self, deployment: PaddleOcrDeploymentService) -> None:
        self._deployment = deployment

    def recognize(self, image_path: Path, *, output_path: Path, timeout: int = 300) -> dict:
        status = self._deployment.status()
        if not status.installed or not status.models_ready:
            raise ValidationError("Local PaddleOCR is not installed. Run one-click setup first.")
        completed = self._deployment._run_worker(
            "ocr",
            timeout=timeout,
            arguments=["--input", str(image_path.resolve()), "--output", str(output_path.resolve())],
        )
        if completed.returncode != 0 or not output_path.is_file():
            raise ValidationError("Local PaddleOCR recognition failed.")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if payload.get("protocol") != SIDECAR_PROTOCOL_VERSION:
            raise ValidationError("Local PaddleOCR protocol version is incompatible.")
        return payload


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValidationError("Downloaded runtime archive contains an unsafe path.") from exc
        package.extractall(destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
