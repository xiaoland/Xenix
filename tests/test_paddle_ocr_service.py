import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.paddle_ocr_service import (
    MAX_SIDECAR_STATUS_BYTES,
    MODEL_MARKER,
    PADDLE_OCR_VERSION,
    PADDLE_VERSION,
    PYTHON_VERSION,
    SIDECAR_PROTOCOL_VERSION,
    PaddleOcrDeploymentService,
    PaddleOcrService,
    PaddleOcrStatus,
    _safe_extract_zip,
)


def _health_payload(**overrides) -> dict:
    payload = {
        "protocol": SIDECAR_PROTOCOL_VERSION,
        "python": PYTHON_VERSION,
        "paddle": PADDLE_VERSION,
        "paddleocr": PADDLE_OCR_VERSION,
    }
    payload.update(overrides)
    return payload


def _warmup_payload(**overrides) -> dict:
    payload = {
        "protocol": SIDECAR_PROTOCOL_VERSION,
        "model_marker": MODEL_MARKER,
        "model_file_count": 3,
        "model_inventory_sha256": "a" * 64,
        "models_ready": True,
    }
    payload.update(overrides)
    return payload


def _manifest_payload(**overrides) -> dict:
    payload = {
        **_health_payload(),
        "model_marker": MODEL_MARKER,
        "model_file_count": 3,
        "model_inventory_sha256": "a" * 64,
        "models_ready": True,
    }
    payload.update(overrides)
    return payload


def _model_payload(**overrides) -> dict:
    payload = {
        "protocol": SIDECAR_PROTOCOL_VERSION,
        "model_file_count": 3,
        "model_inventory_sha256": "a" * 64,
    }
    payload.update(overrides)
    return payload


def _completed(payload: object, *, returncode: int = 0) -> SimpleNamespace:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


def _runtime_deployment(monkeypatch, tmp_path: Path) -> PaddleOcrDeploymentService:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "home"))
    deployment = PaddleOcrDeploymentService(ensure_app_dirs(get_app_paths()))
    deployment._runtime.mkdir(parents=True)  # noqa: SLF001 - isolated runtime fixture
    deployment.python_path.write_bytes(b"python")
    deployment.worker_path.write_text("# worker", encoding="utf-8")
    return deployment


def _prepare_install(monkeypatch, tmp_path: Path) -> PaddleOcrDeploymentService:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    (deployment._runtime / "python313._pth").write_text(  # noqa: SLF001
        "python313.zip\n#import site\n",
        encoding="utf-8",
    )
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
        lambda *args, **kwargs: _completed({}),
    )
    monkeypatch.setattr(
        "xenix.services.paddle_ocr_service.package_root",
        lambda: Path(__file__).resolve().parents[1] / "src" / "xenix",
    )
    return deployment


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


def test_worker_uses_the_real_paddlex_model_cache_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    captured: dict[str, str] = {}

    def run(*_args, **kwargs):
        captured.update(kwargs["env"])
        return _completed(_health_payload())

    monkeypatch.setattr("xenix.services.paddle_ocr_service.subprocess.run", run)

    deployment._run_worker("health", timeout=60)  # noqa: SLF001

    expected = str(deployment._root / "models")  # noqa: SLF001
    assert captured["PADDLE_PDX_CACHE_HOME"] == expected
    assert captured["PADDLEX_HOME"] == expected
    assert captured["PADDLEOCR_HOME"] == expected


def test_status_requires_exact_bounded_health_and_current_model_manifest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    deployment._manifest_path.write_text(  # noqa: SLF001
        json.dumps(_manifest_payload()),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        deployment,
        "_run_worker",
        lambda command, **_kwargs: _completed(
            _model_payload() if command == "models" else _health_payload()
        ),
    )

    status = deployment.status()

    assert status == PaddleOcrStatus(installed=True, models_ready=True)
    assert not hasattr(status, "runtime_path")


@pytest.mark.parametrize(
    ("probe", "expected_detail"),
    [
        (_completed("not-json"), "health_payload_invalid"),
        (_completed("{}\n{}"), "health_payload_invalid"),
        (
            _completed(
                '{"protocol": 1, "protocol": 1, "python": "3.13.13", '
                '"paddle": "3.3.1", "paddleocr": "3.7.0"}'
            ),
            "health_payload_invalid",
        ),
        (_completed("x" * (MAX_SIDECAR_STATUS_BYTES + 1)), "health_payload_invalid"),
        (_completed(_health_payload(protocol=True)), "health_incompatible"),
        (_completed(_health_payload(protocol=999)), "health_incompatible"),
        (_completed(_health_payload(python="3.12.0")), "health_incompatible"),
        (_completed(_health_payload(paddle="0.0.0")), "health_incompatible"),
        (_completed(_health_payload(paddleocr="0.0.0")), "health_incompatible"),
        (_completed({**_health_payload(), "extra": True}), "health_incompatible"),
        (_completed(_health_payload(), returncode=1), "health_check_failed"),
    ],
)
def test_status_rejects_invalid_or_incompatible_health_without_becoming_ready(
    monkeypatch,
    tmp_path: Path,
    probe: SimpleNamespace,
    expected_detail: str,
) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    deployment._manifest_path.write_text(  # noqa: SLF001
        json.dumps(_manifest_payload()),
        encoding="utf-8",
    )
    monkeypatch.setattr(deployment, "_run_worker", lambda *_args, **_kwargs: probe)

    status = deployment.status()

    assert not status.installed
    assert not status.models_ready
    assert status.detail == expected_detail


def test_status_contains_health_timeout_as_safe_not_ready_state(monkeypatch, tmp_path: Path) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("paddle-worker", 60)

    monkeypatch.setattr(deployment, "_run_worker", timeout)

    assert deployment.status() == PaddleOcrStatus(False, False, "health_check_failed")


@pytest.mark.parametrize(
    ("manifest", "expected_detail"),
    [
        (None, "models_manifest_missing"),
        ("not-json", "models_manifest_invalid"),
        (json.dumps([]), "models_manifest_invalid"),
        (json.dumps(_manifest_payload(models_ready="false")), "models_manifest_stale"),
        (json.dumps(_manifest_payload(protocol=999)), "models_manifest_stale"),
        (json.dumps(_manifest_payload(python="3.12.0")), "models_manifest_stale"),
        (json.dumps(_manifest_payload(paddle="0.0.0")), "models_manifest_stale"),
        (json.dumps(_manifest_payload(paddleocr="0.0.0")), "models_manifest_stale"),
        (json.dumps(_manifest_payload(model_marker="old-models")), "models_manifest_stale"),
        (
            json.dumps(_manifest_payload(model_inventory_sha256="z" * 64)),
            "models_manifest_stale",
        ),
    ],
)
def test_status_never_treats_missing_invalid_or_stale_manifest_as_models_ready(
    monkeypatch,
    tmp_path: Path,
    manifest: str | None,
    expected_detail: str,
) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    if manifest is not None:
        deployment._manifest_path.write_text(manifest, encoding="utf-8")  # noqa: SLF001
    monkeypatch.setattr(
        deployment,
        "_run_worker",
        lambda *_args, **_kwargs: _completed(_health_payload()),
    )

    status = deployment.status()

    assert status.installed
    assert not status.models_ready
    assert status.detail == expected_detail


def test_one_click_install_pins_runtime_and_warms_local_models(monkeypatch, tmp_path: Path) -> None:
    deployment = _prepare_install(monkeypatch, tmp_path)
    phases: list[str] = []
    calls: list[tuple[str, int]] = []

    def run_worker(command, *, timeout, arguments=None):
        calls.append((command, timeout))
        if command == "health":
            return _completed(_health_payload())
        if command == "models":
            return _completed(_model_payload())
        return _completed(_warmup_payload())

    monkeypatch.setattr(deployment, "_run_worker", run_worker)

    status = deployment.install(phases.append)

    assert status == PaddleOcrStatus(True, True)
    assert phases == [
        "downloading_python",
        "installing_pip",
        "installing_worker",
        "downloading_models",
        "ready",
    ]
    assert [call[0] for call in calls] == ["health", "warmup", "health", "models"]
    manifest = json.loads(deployment._manifest_path.read_text(encoding="utf-8"))  # noqa: SLF001
    assert manifest == _manifest_payload()


def test_failed_warmup_invalidates_existing_ready_manifest(monkeypatch, tmp_path: Path) -> None:
    deployment = _prepare_install(monkeypatch, tmp_path)
    deployment._manifest_path.write_text(  # noqa: SLF001
        json.dumps(_manifest_payload()),
        encoding="utf-8",
    )

    def run_worker(command, *, timeout, arguments=None):
        if command == "health":
            return _completed(_health_payload())
        return _completed(_warmup_payload(model_marker="stale"))

    monkeypatch.setattr(deployment, "_run_worker", run_worker)

    with pytest.raises(ValidationError, match="models could not be prepared"):
        deployment.install()

    assert not deployment._manifest_path.exists()  # noqa: SLF001


@pytest.mark.parametrize(
    ("model_probe", "expected_detail"),
    [
        (_completed(_model_payload(model_file_count=0)), "models_missing_or_changed"),
        (_completed(_model_payload(model_inventory_sha256="b" * 64)), "models_missing_or_changed"),
        (_completed("not-json"), "models_probe_invalid"),
        (_completed(_model_payload(), returncode=1), "models_probe_failed"),
    ],
)
def test_status_rejects_deleted_changed_or_invalid_model_inventory(
    monkeypatch,
    tmp_path: Path,
    model_probe: SimpleNamespace,
    expected_detail: str,
) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    deployment._manifest_path.write_text(  # noqa: SLF001
        json.dumps(_manifest_payload()),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        deployment,
        "_run_worker",
        lambda command, **_kwargs: model_probe
        if command == "models"
        else _completed(_health_payload()),
    )

    status = deployment.status()

    assert status == PaddleOcrStatus(True, False, expected_detail)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (PaddleOcrStatus(True, True), True),
        (PaddleOcrStatus(True, False), False),
        (PaddleOcrStatus(False, False), False),
    ],
)
def test_ocr_service_readiness_requires_runtime_and_models(status, expected: bool) -> None:
    deployment = SimpleNamespace(status=lambda: status)

    assert PaddleOcrService(deployment).is_ready() is expected


def _recognition_service(
    output_payload: bytes | None,
) -> PaddleOcrService:
    def run_worker(_command, *, timeout, arguments, check_cancelled=None):
        if check_cancelled is not None:
            check_cancelled()
        if output_payload is not None:
            Path(arguments[3]).write_bytes(output_payload)
        return _completed({})

    deployment = SimpleNamespace(
        status=lambda: PaddleOcrStatus(True, True),
        _run_worker=run_worker,
    )
    return PaddleOcrService(deployment)


def test_recognize_returns_a_bounded_exact_worker_envelope(tmp_path: Path) -> None:
    payload = {
        "protocol": SIDECAR_PROTOCOL_VERSION,
        "pages": [
            {
                "res": {
                    "rec_texts": ["门店陈列每周检查两次"],
                    "rec_polys": [[[1, 1], [80, 1], [80, 20], [1, 20]]],
                }
            }
        ],
    }
    service = _recognition_service(json.dumps(payload).encode("utf-8"))

    result = service.recognize(
        tmp_path / "source.png",
        output_path=tmp_path / "result.json",
    )

    assert result == payload


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"protocol": 1}',
        b'{"protocol": true, "pages": []}',
        b'{"protocol": 999, "pages": []}',
        b'{"protocol": 1, "pages": {}}',
        b'{"protocol": 1, "pages": [1]}',
        b'{"protocol": 1, "pages": [], "extra": true}',
        b'{"protocol": 1, "protocol": 1, "pages": []}',
        b'{"protocol": 1, "pages": [], "score": NaN}',
        b"\xff",
    ],
)
def test_recognize_rejects_nonconforming_worker_output_without_exposing_paths(
    tmp_path: Path,
    payload: bytes,
) -> None:
    output_path = tmp_path / "private" / "ocr-secret.json"
    output_path.parent.mkdir()
    service = _recognition_service(payload)

    with pytest.raises(ValidationError, match="returned invalid data") as caught:
        service.recognize(tmp_path / "source.png", output_path=output_path)

    assert str(output_path) not in str(caught.value)


def test_recognize_reads_no_more_than_the_explicit_result_limit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("xenix.services.paddle_ocr_service.MAX_OCR_RESULT_BYTES", 32)
    valid_prefix = b'{"protocol": 1, "pages": []}'
    service = _recognition_service(valid_prefix + b" " * 33)

    with pytest.raises(ValidationError, match="returned invalid data"):
        service.recognize(
            tmp_path / "source.png",
            output_path=tmp_path / "result.json",
        )


def test_recognize_does_not_accept_a_stale_output_file(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    output_path.write_text(
        json.dumps({"protocol": SIDECAR_PROTOCOL_VERSION, "pages": []}),
        encoding="utf-8",
    )
    service = _recognition_service(None)

    with pytest.raises(ValidationError, match="recognition failed"):
        service.recognize(tmp_path / "source.png", output_path=output_path)

    assert not output_path.exists()


def test_recognize_terminates_then_kills_before_propagating_cancellation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    deployment = _runtime_deployment(monkeypatch, tmp_path)
    monkeypatch.setattr(deployment, "status", lambda: PaddleOcrStatus(True, True))

    class WaitingProcess:
        returncode = None
        stdout = None
        stderr = None

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def communicate(self, *, timeout):
            if self.killed:
                self.returncode = -9
                return "", ""
            raise subprocess.TimeoutExpired("paddle-worker", timeout)

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    process = WaitingProcess()
    monkeypatch.setattr(
        "xenix.services.paddle_ocr_service.subprocess.Popen",
        lambda *_args, **_kwargs: process,
    )
    cancellation = RuntimeError("cancelled")
    checks = 0

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1
        if checks == 4:
            raise cancellation

    with pytest.raises(RuntimeError) as caught:
        PaddleOcrService(deployment).recognize(
            tmp_path / "source.png",
            output_path=tmp_path / "result.json",
            timeout=60,
            check_cancelled=check_cancelled,
        )

    assert caught.value is cancellation
    assert process.terminated
    assert process.killed
