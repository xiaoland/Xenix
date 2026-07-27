from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.release_config import ReleaseConfig
from xenix.services.paddle_ocr_service import (
    LocalPaddleOcrBundleSource,
    NATIVE_OCR_PROTOCOL_VERSION,
    PaddleOcrBundleCatalog,
    PaddleOcrDeploymentService,
    PaddleOcrRuntime,
    PaddleOcrService,
    PaddleOcrSession,
    PaddleOcrState,
    PaddleOcrStatus,
    ReleasePaddleOcrBundleSource,
    _safe_extract_zip,
)
from scripts.run_dev import _configure_development_ocr_bundle_source


RUNTIME_ID = "paddle-inference-3.3.0-paddleocr-3.7.0-win-x64"
MODEL_PACK_ID = "pp-ocrv6-medium-zh-en-1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_tree(root: Path) -> dict[str, object]:
    root.mkdir(parents=True)
    (root / "xenix-ocr.exe").write_bytes(b"native-worker")
    for name in ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"):
        model = root / "models" / name
        model.mkdir(parents=True)
        (model / "inference.json").write_text("{}", encoding="utf-8")
    (root / "THIRD_PARTY_NOTICES.txt").write_text("notices", encoding="utf-8")
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    manifest = {
        "schema_version": 1,
        "protocol_version": NATIVE_OCR_PROTOCOL_VERSION,
        "runtime_id": RUNTIME_ID,
        "model_pack_id": MODEL_PACK_ID,
        "engine": "paddle-inference",
        "engine_version": "3.3.0",
        "architecture": "windows-x86_64",
        "executable": "xenix-ocr.exe",
        "models": {
            "detection": "models/PP-OCRv6_medium_det",
            "recognition": "models/PP-OCRv6_medium_rec",
        },
        "files": files,
    }
    (root / "runtime.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return manifest


def _catalog(archive: Path) -> PaddleOcrBundleCatalog:
    return PaddleOcrBundleCatalog(
        artifact_name=archive.name,
        artifact_bytes=archive.stat().st_size,
        artifact_sha256=_sha256(archive),
        protocol_version=NATIVE_OCR_PROTOCOL_VERSION,
        runtime_id=RUNTIME_ID,
        model_pack_id=MODEL_PACK_ID,
    )


def _write_runtime_archive(source: Path, archive: Path) -> None:
    with ZipFile(archive, "w") as package:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                package.write(
                    path,
                    (Path("xenix-knowledge-ocr") / path.relative_to(source)).as_posix(),
                )


def _paths(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "home"))
    return ensure_app_dirs(get_app_paths())


def test_runtime_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    with ZipFile(archive, "w") as package:
        package.writestr("../escape.txt", "bad")

    with pytest.raises((ValidationError, ValueError)):
        _safe_extract_zip(archive, tmp_path / "runtime")


def test_catalog_is_strict_and_protocol_versioned() -> None:
    payload = {
        "schema_version": 1,
        "artifact_name": "ocr.zip",
        "artifact_bytes": 1,
        "artifact_sha256": "a" * 64,
        "protocol_version": 2,
        "runtime_id": RUNTIME_ID,
        "model_pack_id": MODEL_PACK_ID,
    }
    assert PaddleOcrBundleCatalog.from_payload(payload).runtime_id == RUNTIME_ID
    with pytest.raises(ValueError):
        PaddleOcrBundleCatalog.from_payload({**payload, "protocol_version": 1})
    with pytest.raises(ValueError):
        PaddleOcrBundleCatalog.from_payload({**payload, "extra": True})


def test_status_snapshot_uses_a_fresh_verification_record_without_rescanning_bundle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(monkeypatch, tmp_path)
    empty = PaddleOcrDeploymentService(paths)
    assert empty.status_snapshot().state is PaddleOcrState.NOT_INSTALLED

    root = paths.cache / "knowledge-ocr"
    generation = root / "bundles" / "generation-1"
    _runtime_tree(generation)
    (root / "active.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generation_id": "generation-1",
                "runtime_id": RUNTIME_ID,
                "model_pack_id": MODEL_PACK_ID,
                "manifest_sha256": _sha256(generation / "runtime.json"),
                "artifact_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    deployment = PaddleOcrDeploymentService(paths)
    unverified = deployment.status_snapshot()
    assert unverified.state is PaddleOcrState.CHECKING
    assert unverified.reason_code == "verification_required"
    runtime = deployment._resolve_active_runtime()  # noqa: SLF001 - verification fixture
    deployment._write_verification_record(runtime)  # noqa: SLF001 - verification fixture

    calls: list[Path] = []
    original = __import__("xenix.services.paddle_ocr_service", fromlist=["_sha256"])._sha256

    def record_hash(path: Path) -> str:
        calls.append(path)
        return original(path)

    monkeypatch.setattr("xenix.services.paddle_ocr_service._sha256", record_hash)
    status = deployment.status_snapshot()

    assert status == PaddleOcrStatus(
        PaddleOcrState.READY,
        runtime_id=RUNTIME_ID,
        model_pack_id=MODEL_PACK_ID,
        generation_id="generation-1",
    )
    assert calls == [generation / "runtime.json"]

    verification_path = root / "verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["verified_at"] = 1
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    stale = deployment.status_snapshot()
    assert stale.state is PaddleOcrState.CHECKING
    assert stale.reason_code == "verification_stale"

    monkeypatch.setattr(deployment, "_self_test", lambda _runtime: None)
    assert deployment.verify_active().state is PaddleOcrState.READY
    assert deployment.status_snapshot().state is PaddleOcrState.READY


def test_local_bundle_source_verifies_and_atomically_activates_one_bundle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(monkeypatch, tmp_path)
    source = tmp_path / "bundle-source" / "xenix-knowledge-ocr"
    _runtime_tree(source)
    archive = tmp_path / "xenix-knowledge-ocr.zip"
    _write_runtime_archive(source, archive)
    catalog = _catalog(archive)
    deployment = PaddleOcrDeploymentService(
        paths,
        bundle_source=LocalPaddleOcrBundleSource(catalog, archive),
    )
    self_tests: list[PaddleOcrRuntime] = []
    monkeypatch.setattr(
        deployment,
        "_self_test",
        lambda runtime: self_tests.append(runtime),
    )
    phases: list[str] = []

    status = deployment.install(phases.append)

    assert status.state is PaddleOcrState.READY
    assert phases == [
        "downloading_bundle",
        "extracting_bundle",
        "verifying_bundle",
        "self_testing",
        "activating_bundle",
        "ready",
    ]
    assert len(self_tests) == 1
    tested_runtime = self_tests[0]
    assert tested_runtime.generation_path.parent == paths.cache / "knowledge-ocr" / "bundles"
    assert tested_runtime.generation_path.name.startswith("ocr-")
    assert len(tested_runtime.generation_path.name) == 36
    assert deployment.open_runtime() == tested_runtime


def test_activation_self_test_failure_does_not_publish_or_retain_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(monkeypatch, tmp_path)
    source = tmp_path / "bundle-source" / "xenix-knowledge-ocr"
    _runtime_tree(source)
    archive = tmp_path / "xenix-knowledge-ocr.zip"
    _write_runtime_archive(source, archive)
    deployment = PaddleOcrDeploymentService(
        paths,
        bundle_source=LocalPaddleOcrBundleSource(_catalog(archive), archive),
    )

    def reject_final_runtime(runtime: PaddleOcrRuntime) -> None:
        assert runtime.generation_path.parent == paths.cache / "knowledge-ocr" / "bundles"
        raise ValidationError(
            "Final runtime path failed.",
            error_code="knowledge_ocr_self_test_failed",
        )

    monkeypatch.setattr(deployment, "_self_test", reject_final_runtime)

    with pytest.raises(ValidationError) as caught:
        deployment.install()

    assert caught.value.error_code == "knowledge_ocr_self_test_failed"
    assert not (paths.cache / "knowledge-ocr" / "active.json").exists()
    assert list((paths.cache / "knowledge-ocr" / "bundles").iterdir()) == []


def test_local_bundle_source_rejects_an_archive_that_misses_catalog_hash(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(monkeypatch, tmp_path)
    source = tmp_path / "bundle-source" / "xenix-knowledge-ocr"
    _runtime_tree(source)
    archive = tmp_path / "xenix-knowledge-ocr.zip"
    _write_runtime_archive(source, archive)
    catalog = _catalog(archive)
    archive.write_bytes(archive.read_bytes() + b"unexpected")
    deployment = PaddleOcrDeploymentService(
        paths,
        bundle_source=LocalPaddleOcrBundleSource(catalog, archive),
    )

    with pytest.raises(ValidationError) as caught:
        deployment.install()

    assert caught.value.error_code == "knowledge_ocr_bundle_integrity_failed"
    assert not (paths.cache / "knowledge-ocr" / "active.json").exists()


def test_release_bundle_source_downloads_and_activates_the_catalog_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(monkeypatch, tmp_path)
    source = tmp_path / "bundle-source" / "xenix-knowledge-ocr"
    _runtime_tree(source)
    archive = tmp_path / "xenix-knowledge-ocr.zip"
    _write_runtime_archive(source, archive)
    catalog = _catalog(archive)
    requested: list[tuple[str, int]] = []

    def fetch(url: str, *, timeout: int) -> io.BytesIO:
        requested.append((url, timeout))
        return io.BytesIO(archive.read_bytes())

    monkeypatch.setattr("xenix.services.paddle_ocr_service.urllib.request.urlopen", fetch)
    deployment = PaddleOcrDeploymentService(
        paths,
        bundle_source=ReleasePaddleOcrBundleSource(
            catalog,
            ReleaseConfig(releases_oss_public_url="https://releases.example.test"),
        ),
    )
    monkeypatch.setattr(deployment, "_self_test", lambda _runtime: None)

    assert deployment.install().state is PaddleOcrState.READY
    assert requested == [
        (f"https://releases.example.test/{catalog.artifact_name}", 120)
    ]


def test_release_bundle_source_requires_a_release_origin(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(monkeypatch, tmp_path)
    catalog = PaddleOcrBundleCatalog(
        artifact_name="xenix-knowledge-ocr.zip",
        artifact_bytes=1,
        artifact_sha256="a" * 64,
        protocol_version=NATIVE_OCR_PROTOCOL_VERSION,
        runtime_id=RUNTIME_ID,
        model_pack_id=MODEL_PACK_ID,
    )
    deployment = PaddleOcrDeploymentService(
        paths,
        bundle_source=ReleasePaddleOcrBundleSource(catalog, ReleaseConfig()),
    )

    with pytest.raises(ValidationError) as caught:
        deployment.install()

    assert caught.value.error_code == "knowledge_ocr_download_unavailable"


def test_run_dev_composes_dist_archive_as_a_local_bundle_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    source = project_root / "bundle-source" / "xenix-knowledge-ocr"
    _runtime_tree(source)
    archive = (
        project_root
        / "dist"
        / "knowledge-ocr"
        / "xenix-knowledge-ocr.zip"
    )
    archive.parent.mkdir(parents=True)
    _write_runtime_archive(source, archive)
    catalog = _catalog(archive)
    (archive.parent / "runtime_catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_name": catalog.artifact_name,
                "artifact_bytes": catalog.artifact_bytes,
                "artifact_sha256": catalog.artifact_sha256,
                "protocol_version": catalog.protocol_version,
                "runtime_id": catalog.runtime_id,
                "model_pack_id": catalog.model_pack_id,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("XENIX_KNOWLEDGE_OCR_CATALOG", raising=False)
    monkeypatch.delenv("XENIX_KNOWLEDGE_OCR_ARTIFACT", raising=False)

    _configure_development_ocr_bundle_source(project_root)

    paths = _paths(monkeypatch, tmp_path)
    deployment = PaddleOcrDeploymentService(paths)
    assert isinstance(deployment.bundle_source, LocalPaddleOcrBundleSource)
    assert deployment.bundle_source.catalog == catalog
    assert deployment.bundle_source.artifact_path == archive


def test_corrupt_active_pointer_requires_repair(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(monkeypatch, tmp_path)
    root = paths.cache / "knowledge-ocr"
    root.mkdir(parents=True)
    (root / "active.json").write_text("not-json", encoding="utf-8")

    status = PaddleOcrDeploymentService(paths).status_snapshot()

    assert status.state is PaddleOcrState.REPAIR_REQUIRED
    assert status.reason_code == "runtime_manifest_invalid"


def test_ocr_service_readiness_requires_ready_state() -> None:
    for state, expected in (
        (PaddleOcrState.READY, True),
        (PaddleOcrState.REPAIR_REQUIRED, False),
        (PaddleOcrState.NOT_INSTALLED, False),
    ):
        deployment = SimpleNamespace(
            status_snapshot=lambda state=state: PaddleOcrStatus(state)
        )
        assert PaddleOcrService(deployment).is_ready() is expected


def test_native_session_reuses_one_process_and_normalizes_regions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    worker = tmp_path / "fake_worker.py"
    worker.write_text(
        """
import json, struct, sys
def read_exact(n):
    data = b''
    while len(data) < n:
        chunk = sys.stdin.buffer.read(n-len(data))
        if not chunk: raise SystemExit(0)
        data += chunk
    return data
def receive():
    return json.loads(read_exact(struct.unpack('>I', read_exact(4))[0]))
def send(value):
    data=json.dumps(value,separators=(',',':')).encode()
    sys.stdout.buffer.write(struct.pack('>I',len(data))+data); sys.stdout.buffer.flush()
while True:
    request=receive(); op=request['operation']; rid=request['request_id']
    if op=='version': result={'protocol_version':2,'runtime_id':'paddle-inference-3.3.0-paddleocr-3.7.0-win-x64'}
    elif op=='initialize': result={'initialized':True}
    elif op=='self_test': result={'success':True}
    elif op=='recognize': result={'regions':[{'text':'登机牌 BOARDING','confidence':0.99,'polygon':[[0,0],[10,0],[10,4],[0,4]]}]}
    elif op=='shutdown':
        send({'protocol_version':2,'request_id':rid,'ok':True,'result':{'shutdown':True}}); break
    send({'protocol_version':2,'request_id':rid,'ok':True,'result':result})
""".strip(),
        encoding="utf-8",
    )
    real_popen = subprocess.Popen
    launches: list[list[str]] = []

    def launch(_command, **kwargs):
        command = [sys.executable, "-I", str(worker)]
        launches.append(command)
        return real_popen(command, **kwargs)

    monkeypatch.setattr("xenix.services.paddle_ocr_service.subprocess.Popen", launch)
    runtime_root = tmp_path / "runtime"
    detection = runtime_root / "models" / "det"
    recognition = runtime_root / "models" / "rec"
    detection.mkdir(parents=True)
    recognition.mkdir(parents=True)
    image = tmp_path / "work" / "page.png"
    image.parent.mkdir()
    image.write_bytes(b"image")
    runtime = PaddleOcrRuntime(
        generation_id="generation",
        generation_path=runtime_root,
        executable_path=runtime_root / "xenix-ocr.exe",
        detection_model_path=detection,
        recognition_model_path=recognition,
        runtime_id=RUNTIME_ID,
        model_pack_id=MODEL_PACK_ID,
        engine_version="3.3.0",
        manifest_sha256="a" * 64,
    )

    with PaddleOcrSession(runtime, allowed_root=image.parent, log_path=tmp_path / "ocr.log") as session:
        first_pid = session.pid
        first = session.recognize(image)
        second = session.recognize(image)

    assert len(launches) == 1
    assert first_pid is not None
    assert first == second == {
        "protocol": 2,
        "pages": [
            {
                "regions": [
                    {
                        "text": "登机牌 BOARDING",
                        "confidence": 0.99,
                        "polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 4.0], [0.0, 4.0]],
                    }
                ]
            }
        ],
    }


def test_native_session_rejects_input_outside_import_staging(tmp_path: Path) -> None:
    runtime = PaddleOcrRuntime(
        "generation",
        tmp_path,
        tmp_path / "xenix-ocr.exe",
        tmp_path / "det",
        tmp_path / "rec",
        RUNTIME_ID,
        MODEL_PACK_ID,
        "3.3.0",
        "a" * 64,
    )
    session = PaddleOcrSession(runtime, allowed_root=tmp_path / "allowed", log_path=tmp_path / "ocr.log")
    with pytest.raises(ValidationError) as caught:
        session.recognize(tmp_path / "outside.png")
    assert caught.value.error_code == "knowledge_ocr_input_outside_staging"
