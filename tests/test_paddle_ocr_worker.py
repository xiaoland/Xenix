import json
import os
import subprocess
import sys
from pathlib import Path

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.paddle_ocr_service import (
    MODEL_MARKER,
    PADDLE_OCR_VERSION,
    PADDLE_VERSION,
    PYTHON_VERSION,
    SIDECAR_PROTOCOL_VERSION,
    PaddleOcrDeploymentService,
    PaddleOcrStatus,
)


WORKER_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "xenix"
    / "resources"
    / "knowledge_ocr"
    / "paddle_worker.py"
)
ORIGINAL_MODEL_BYTES = b"original-model-bytes"
TAMPERED_MODEL_BYTES = b"tampered-model-bytes"


def _run_models(model_cache: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PADDLE_PDX_CACHE_HOME"] = str(model_cache)
    environment["PADDLEX_HOME"] = str(model_cache)
    environment["PADDLEOCR_HOME"] = str(model_cache)
    return subprocess.run(
        [sys.executable, "-I", str(WORKER_PATH), "models"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env=environment,
    )


def test_models_command_fingerprints_same_size_content_changes_offline(tmp_path: Path) -> None:
    assert len(ORIGINAL_MODEL_BYTES) == len(TAMPERED_MODEL_BYTES)
    model_cache = tmp_path / "models"
    model_file = model_cache / "text-recognition" / "model.pdparams"
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(ORIGINAL_MODEL_BYTES)

    before = _run_models(model_cache)
    model_file.write_bytes(TAMPERED_MODEL_BYTES)
    after = _run_models(model_cache)

    assert before.returncode == 0
    assert after.returncode == 0
    before_payload = json.loads(before.stdout)
    after_payload = json.loads(after.stdout)
    assert before_payload.keys() == {
        "protocol",
        "model_file_count",
        "model_inventory_sha256",
    }
    assert before_payload["protocol"] == SIDECAR_PROTOCOL_VERSION
    assert before_payload["model_file_count"] == after_payload["model_file_count"] == 1
    assert before_payload["model_inventory_sha256"] != after_payload["model_inventory_sha256"]


def test_status_consumes_the_actual_offline_models_inventory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "home"))

    class OfflineInventoryDeployment(PaddleOcrDeploymentService):
        @property
        def python_path(self) -> Path:
            return Path(sys.executable)

        @property
        def worker_path(self) -> Path:
            return WORKER_PATH

        def _run_worker(self, command, *, timeout, arguments=None, check_cancelled=None):
            if command == "health":
                return subprocess.CompletedProcess(
                    ["offline-health"],
                    0,
                    json.dumps(
                        {
                            "protocol": SIDECAR_PROTOCOL_VERSION,
                            "python": PYTHON_VERSION,
                            "paddle": PADDLE_VERSION,
                            "paddleocr": PADDLE_OCR_VERSION,
                        }
                    ),
                    "",
                )
            return super()._run_worker(
                command,
                timeout=timeout,
                arguments=arguments,
                check_cancelled=check_cancelled,
            )

    deployment = OfflineInventoryDeployment(ensure_app_dirs(get_app_paths()))
    model_file = deployment._root / "models" / "text-recognition" / "model.pdparams"  # noqa: SLF001
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(ORIGINAL_MODEL_BYTES)
    inventory_probe = _run_models(deployment._root / "models")  # noqa: SLF001
    assert inventory_probe.returncode == 0
    inventory = json.loads(inventory_probe.stdout)
    deployment._manifest_path.write_text(  # noqa: SLF001
        json.dumps(
            {
                "protocol": SIDECAR_PROTOCOL_VERSION,
                "python": PYTHON_VERSION,
                "paddle": PADDLE_VERSION,
                "paddleocr": PADDLE_OCR_VERSION,
                "model_marker": MODEL_MARKER,
                "model_file_count": inventory["model_file_count"],
                "model_inventory_sha256": inventory["model_inventory_sha256"],
                "models_ready": True,
            }
        ),
        encoding="utf-8",
    )

    assert deployment.status() == PaddleOcrStatus(True, True)

    model_file.write_bytes(TAMPERED_MODEL_BYTES)

    assert deployment.status() == PaddleOcrStatus(True, False, "models_missing_or_changed")
