import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.knowledge_packaged_smoke import run_knowledge_packaged_smoke


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
