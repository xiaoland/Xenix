from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
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
MODEL_INVENTORY_VERSION = 2
MAX_SIDECAR_STATUS_BYTES = 4 * 1024
MAX_OCR_RESULT_BYTES = 16 * 1024 * 1024
SIDECAR_POLL_INTERVAL_SECONDS = 0.1
SIDECAR_TERMINATE_GRACE_SECONDS = 0.5
MODEL_MARKER = (
    f"xenix-paddleocr-models:v{SIDECAR_PROTOCOL_VERSION}:"
    f"python-{PYTHON_VERSION}:paddle-{PADDLE_VERSION}:paddleocr-{PADDLE_OCR_VERSION}:"
    f"inventory-{MODEL_INVENTORY_VERSION}"
)

_HEALTH_KEYS = frozenset({"protocol", "python", "paddle", "paddleocr"})
_MANIFEST_KEYS = frozenset(
    {
        "protocol",
        "python",
        "paddle",
        "paddleocr",
        "model_marker",
        "model_file_count",
        "model_inventory_sha256",
        "models_ready",
    }
)
_WARMUP_KEYS = frozenset(
    {
        "protocol",
        "model_marker",
        "model_file_count",
        "model_inventory_sha256",
        "models_ready",
    }
)
_MODEL_KEYS = frozenset({"protocol", "model_file_count", "model_inventory_sha256"})
_OCR_KEYS = frozenset({"protocol", "pages"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class PaddleOcrStatus:
    installed: bool
    models_ready: bool
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
            return PaddleOcrStatus(False, False, "runtime_missing")
        try:
            probe = self._run_worker("health", timeout=60)
        except (OSError, subprocess.SubprocessError):
            return PaddleOcrStatus(False, False, "health_check_failed")
        if probe.returncode != 0:
            return PaddleOcrStatus(False, False, "health_check_failed")
        try:
            health = _bounded_json_object(probe.stdout)
        except (RecursionError, TypeError, ValueError, UnicodeError):
            return PaddleOcrStatus(False, False, "health_payload_invalid")
        if not _health_payload_is_compatible(health):
            return PaddleOcrStatus(False, False, "health_incompatible")

        if not self._manifest_path.is_file():
            return PaddleOcrStatus(True, False, "models_manifest_missing")
        try:
            manifest = _bounded_json_file(self._manifest_path)
        except (OSError, RecursionError, TypeError, ValueError, UnicodeError):
            return PaddleOcrStatus(True, False, "models_manifest_invalid")
        if not _manifest_is_current(manifest):
            return PaddleOcrStatus(True, False, "models_manifest_stale")
        try:
            model_probe = self._run_worker("models", timeout=60)
        except (OSError, subprocess.SubprocessError):
            return PaddleOcrStatus(True, False, "models_probe_failed")
        if model_probe.returncode != 0:
            return PaddleOcrStatus(True, False, "models_probe_failed")
        try:
            model_inventory = _bounded_json_object(model_probe.stdout)
        except (RecursionError, TypeError, ValueError, UnicodeError):
            return PaddleOcrStatus(True, False, "models_probe_invalid")
        if not _model_inventory_matches_manifest(model_inventory, manifest):
            return PaddleOcrStatus(True, False, "models_missing_or_changed")
        return PaddleOcrStatus(True, True)

    def install(self, progress: Callable[[str], None] | None = None) -> PaddleOcrStatus:
        report = progress or (lambda _phase: None)
        self._root.mkdir(parents=True, exist_ok=True)
        self._downloads.mkdir(parents=True, exist_ok=True)
        self._manifest_path.unlink(missing_ok=True)
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
        try:
            health = self._run_worker("health", timeout=120)
        except (OSError, subprocess.SubprocessError):
            raise ValidationError("PaddleOCR local runtime health check failed.") from None
        if health.returncode != 0 or not _completed_health_is_compatible(health):
            raise ValidationError("PaddleOCR local runtime health check failed.")

        report("downloading_models")
        try:
            warmup = self._run_worker("warmup", timeout=1800)
        except (OSError, subprocess.SubprocessError):
            raise ValidationError("PaddleOCR local models could not be prepared.") from None
        warmup_payload = _completed_warmup_payload(warmup) if warmup.returncode == 0 else None
        if warmup_payload is None:
            raise ValidationError("PaddleOCR local models could not be prepared.")
        manifest = {
            "protocol": SIDECAR_PROTOCOL_VERSION,
            "python": PYTHON_VERSION,
            "paddle": PADDLE_VERSION,
            "paddleocr": PADDLE_OCR_VERSION,
            "model_marker": MODEL_MARKER,
            "model_file_count": warmup_payload["model_file_count"],
            "model_inventory_sha256": warmup_payload["model_inventory_sha256"],
            "models_ready": True,
        }
        manifest_temp = self._manifest_path.with_suffix(".json.tmp")
        manifest_temp.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        os.replace(manifest_temp, self._manifest_path)

        verified = self.status()
        if not verified.installed or not verified.models_ready:
            self._manifest_path.unlink(missing_ok=True)
            raise ValidationError("PaddleOCR local runtime readiness could not be verified.")
        report("ready")
        return verified

    def _run_worker(
        self,
        command: str,
        *,
        timeout: int,
        arguments: list[str] | None = None,
        check_cancelled: Callable[[], object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(self._root)
        environment["USERPROFILE"] = str(self._root)
        model_cache = str(self._root / "models")
        environment["PADDLE_PDX_CACHE_HOME"] = model_cache
        environment["PADDLEX_HOME"] = model_cache
        environment["PADDLEOCR_HOME"] = model_cache
        worker_command = [str(self.python_path), str(self.worker_path), command, *(arguments or ())]
        if check_cancelled is None:
            return subprocess.run(
                worker_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=environment,
            )

        check_cancelled()
        process = subprocess.Popen(
            worker_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        deadline = time.monotonic() + timeout
        try:
            while True:
                check_cancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(worker_command, timeout)
                try:
                    stdout, stderr = process.communicate(
                        timeout=min(SIDECAR_POLL_INTERVAL_SECONDS, remaining)
                    )
                except subprocess.TimeoutExpired:
                    continue
                check_cancelled()
                return subprocess.CompletedProcess(
                    worker_command,
                    process.returncode,
                    stdout,
                    stderr,
                )
        except BaseException:
            try:
                _stop_worker_process(process)
            except BaseException:
                pass
            raise

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

    def is_ready(self) -> bool:
        status = self._deployment.status()
        return status.installed and status.models_ready

    def recognize(
        self,
        image_path: Path,
        *,
        output_path: Path,
        timeout: int = 300,
        check_cancelled: Callable[[], object] | None = None,
    ) -> dict[str, object]:
        if check_cancelled is not None:
            check_cancelled()
        if not self.is_ready():
            raise ValidationError("Local PaddleOCR is not installed. Run one-click setup first.")
        if check_cancelled is not None:
            check_cancelled()

        callback_error: BaseException | None = None

        def guarded_cancel_check() -> object:
            nonlocal callback_error
            assert check_cancelled is not None
            try:
                return check_cancelled()
            except BaseException as exc:
                callback_error = exc
                raise

        try:
            arguments = ["--input", str(image_path.resolve()), "--output", str(output_path.resolve())]
            output_path.unlink(missing_ok=True)
            if check_cancelled is None:
                completed = self._deployment._run_worker(
                    "ocr",
                    timeout=timeout,
                    arguments=arguments,
                )
            else:
                completed = self._deployment._run_worker(
                    "ocr",
                    timeout=timeout,
                    arguments=arguments,
                    check_cancelled=guarded_cancel_check,
                )
        except BaseException as exc:
            if exc is callback_error:
                raise
            if isinstance(exc, (OSError, subprocess.SubprocessError)):
                raise ValidationError("Local PaddleOCR recognition failed.") from None
            raise
        if completed.returncode != 0 or not output_path.is_file():
            raise ValidationError("Local PaddleOCR recognition failed.")
        try:
            payload = _bounded_json_file(output_path, max_bytes=MAX_OCR_RESULT_BYTES)
        except (OSError, RecursionError, TypeError, ValueError, UnicodeError):
            raise ValidationError("Local PaddleOCR recognition returned invalid data.") from None
        if not _ocr_payload_is_valid(payload):
            raise ValidationError("Local PaddleOCR recognition returned invalid data.")
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


def _stop_worker_process(process: subprocess.Popen[str]) -> None:
    try:
        process_running = process.poll() is None
    except OSError:
        process_running = True
    if process_running:
        try:
            process.terminate()
        except OSError:
            pass
    try:
        process.communicate(timeout=SIDECAR_TERMINATE_GRACE_SECONDS)
    except (OSError, ValueError):
        pass
    except subprocess.TimeoutExpired:
        try:
            process_running = process.poll() is None
        except OSError:
            process_running = True
        if process_running:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.communicate(timeout=SIDECAR_TERMINATE_GRACE_SECONDS)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def _bounded_json_file(
    path: Path,
    *,
    max_bytes: int = MAX_SIDECAR_STATUS_BYTES,
) -> dict[str, object]:
    with path.open("rb") as source:
        payload = source.read(max_bytes + 1)
    if not payload or len(payload) > max_bytes:
        raise ValueError("Sidecar JSON payload is outside the supported bound.")
    return _bounded_json_object(payload.decode("utf-8"), max_bytes=max_bytes)


def _bounded_json_object(
    raw: object,
    *,
    max_bytes: int = MAX_SIDECAR_STATUS_BYTES,
) -> dict[str, object]:
    if not isinstance(raw, str):
        raise TypeError("Sidecar JSON payload must be text.")
    encoded = raw.encode("utf-8")
    if not encoded or len(encoded) > max_bytes:
        raise ValueError("Sidecar JSON payload is outside the supported bound.")

    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON constant is not supported: {value}")

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        payload: dict[str, object] = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError("Duplicate sidecar JSON keys are not supported.")
            payload[key] = value
        return payload

    payload = json.loads(
        raw,
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_keys,
    )
    if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
        raise TypeError("Sidecar JSON payload must be an object.")
    return payload


def _health_payload_is_compatible(payload: dict[str, object]) -> bool:
    return (
        payload.keys() == _HEALTH_KEYS
        and type(payload.get("protocol")) is int
        and payload["protocol"] == SIDECAR_PROTOCOL_VERSION
        and type(payload.get("python")) is str
        and payload["python"] == PYTHON_VERSION
        and type(payload.get("paddle")) is str
        and payload["paddle"] == PADDLE_VERSION
        and type(payload.get("paddleocr")) is str
        and payload["paddleocr"] == PADDLE_OCR_VERSION
    )


def _manifest_is_current(payload: dict[str, object]) -> bool:
    return (
        payload.keys() == _MANIFEST_KEYS
        and type(payload.get("protocol")) is int
        and payload["protocol"] == SIDECAR_PROTOCOL_VERSION
        and type(payload.get("python")) is str
        and payload["python"] == PYTHON_VERSION
        and type(payload.get("paddle")) is str
        and payload["paddle"] == PADDLE_VERSION
        and type(payload.get("paddleocr")) is str
        and payload["paddleocr"] == PADDLE_OCR_VERSION
        and type(payload.get("model_marker")) is str
        and payload["model_marker"] == MODEL_MARKER
        and type(payload.get("model_file_count")) is int
        and payload["model_file_count"] > 0
        and type(payload.get("model_inventory_sha256")) is str
        and _SHA256_PATTERN.fullmatch(payload["model_inventory_sha256"]) is not None
        and payload.get("models_ready") is True
    )


def _warmup_payload_is_current(payload: dict[str, object]) -> bool:
    return (
        payload.keys() == _WARMUP_KEYS
        and type(payload.get("protocol")) is int
        and payload["protocol"] == SIDECAR_PROTOCOL_VERSION
        and type(payload.get("model_marker")) is str
        and payload["model_marker"] == MODEL_MARKER
        and type(payload.get("model_file_count")) is int
        and payload["model_file_count"] > 0
        and type(payload.get("model_inventory_sha256")) is str
        and _SHA256_PATTERN.fullmatch(payload["model_inventory_sha256"]) is not None
        and payload.get("models_ready") is True
    )


def _model_inventory_matches_manifest(
    payload: dict[str, object],
    manifest: dict[str, object],
) -> bool:
    return (
        payload.keys() == _MODEL_KEYS
        and type(payload.get("protocol")) is int
        and payload["protocol"] == SIDECAR_PROTOCOL_VERSION
        and type(payload.get("model_file_count")) is int
        and payload["model_file_count"] > 0
        and type(payload.get("model_inventory_sha256")) is str
        and _SHA256_PATTERN.fullmatch(payload["model_inventory_sha256"]) is not None
        and payload["model_file_count"] == manifest.get("model_file_count")
        and payload["model_inventory_sha256"] == manifest.get("model_inventory_sha256")
    )


def _ocr_payload_is_valid(payload: dict[str, object]) -> bool:
    pages = payload.get("pages")
    return (
        payload.keys() == _OCR_KEYS
        and type(payload.get("protocol")) is int
        and payload["protocol"] == SIDECAR_PROTOCOL_VERSION
        and isinstance(pages, list)
        and all(isinstance(page, dict) for page in pages)
    )


def _completed_health_is_compatible(completed: object) -> bool:
    try:
        return _health_payload_is_compatible(_bounded_json_object(getattr(completed, "stdout", None)))
    except (RecursionError, TypeError, ValueError, UnicodeError):
        return False


def _completed_warmup_payload(completed: object) -> dict[str, object] | None:
    try:
        payload = _bounded_json_object(getattr(completed, "stdout", None))
        return payload if _warmup_payload_is_current(payload) else None
    except (RecursionError, TypeError, ValueError, UnicodeError):
        return None
