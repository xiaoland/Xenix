import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_packaged_smoke import (
    _wait_for_derivation_handoff,
    run_knowledge_packaged_smoke,
)


def _load_packaged_smoke_verifier():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_packaged_smoke.py"
    spec = importlib.util.spec_from_file_location(
        "xenix_verify_packaged_smoke_for_test",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaged_smoke_failure_diagnostic_is_bounded_and_redacted(
    tmp_path: Path,
) -> None:
    verifier = _load_packaged_smoke_verifier()
    runtime_root = tmp_path / "runtime"
    log_path = runtime_root / "logs" / "xenix.log"
    log_path.parent.mkdir(parents=True)
    secret = "release-secret-value"
    log_path.write_text(
        "\n".join(
            (
                json.dumps({"event": "ordinary", "level": "info"}),
                json.dumps(
                    {
                        "event": "Xenix smoke test failed",
                        "exception": (
                            f"RuntimeError: {secret} at "
                            f"{runtime_root / 'temp' / 'source.docx'}"
                        ),
                        "level": "error",
                        "logger": "xenix.app",
                    }
                ),
            )
        ),
        encoding="utf-8",
    )
    marker_path = runtime_root / "state" / "knowledge-smoke.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "spawned_docx_import": True,
                "private_detail": secret,
            }
        ),
        encoding="utf-8",
    )

    diagnostic = verifier.packaged_smoke_failure_diagnostic(
        runtime_root,
        {"XENIX_TRIAL_LLM_API_KEY": secret},
    )
    rendered = json.dumps(diagnostic, sort_keys=True)

    assert secret not in rendered
    assert str(runtime_root) not in rendered
    assert "<runtime>" in rendered
    assert diagnostic["knowledge_marker"] == {
        "schema_version": 1,
        "spawned_docx_import": True,
    }
    assert len(diagnostic["error_events"]) == 1


def test_importing_knowledge_smoke_does_not_pollute_svg_namespace() -> None:
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_root, environment.get("PYTHONPATH")) if part
    )
    script = """
import xml.etree.ElementTree as ET
from xenix.services import analysis_graph
import xenix.services.knowledge_packaged_smoke
root = ET.Element(f\"{{{analysis_graph._SVG_NS}}}svg\")
assert ET.tostring(root, encoding=\"unicode\").startswith(\"<svg\")
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


def test_packaged_smoke_waits_for_async_derivation_handoff() -> None:
    expected = object()

    class EventuallyVisibleDerivation:
        def __init__(self) -> None:
            self.calls = 0

        def status_for_import(self, import_id: str):
            assert import_id == "import-1"
            self.calls += 1
            return expected if self.calls > 1 else None

    service = EventuallyVisibleDerivation()

    assert (
        _wait_for_derivation_handoff(
            service,
            "import-1",
            failure_message="handoff unavailable",
            timeout=1,
        )
        is expected
    )
    assert service.calls == 2


def test_knowledge_packaged_smoke_exercises_native_and_data_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())

    run_knowledge_packaged_smoke(paths)

    marker = json.loads((paths.state / "knowledge-smoke.json").read_text())
    assert marker["spawned_docx_import"] is True
    assert marker["spawned_pptx_import"] is True
    assert marker["document_removal"] is True
    assert marker["same_sha_reimport"] is True


@pytest.mark.skipif(
    not os.environ.get("XENIX_KNOWLEDGE_OCR_SMOKE_ARCHIVE")
    or not os.environ.get("XENIX_KNOWLEDGE_OCR_SMOKE_IMAGE"),
    reason="real native OCR acceptance inputs are not configured",
)
def test_knowledge_packaged_smoke_reaches_lookup_through_real_native_ocr(
    monkeypatch,
) -> None:
    with TemporaryDirectory(prefix="xk-real-") as temporary:
        monkeypatch.setenv("XENIX_APP_HOME", str(Path(temporary) / "h"))
        paths = ensure_app_dirs(get_app_paths())

        run_knowledge_packaged_smoke(paths)

        marker = json.loads((paths.state / "knowledge-smoke.json").read_text())
        assert marker["paddle_native_activation"] is True
        assert marker["paddle_native_retrieval"] is True
