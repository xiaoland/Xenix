from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_knowledge_ocr_runtime.py"


def _build_module():
    spec = importlib.util.spec_from_file_location("xenix_ocr_build_for_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_runtime_lock_pins_every_download_and_compatibility_patch() -> None:
    build = _build_module()
    lock = build.load_lock()

    assert lock["paddleocr"]["commit"] == "b03f46425e8ff4442b268ce449e3eef758146cd4"
    assert lock["runtime_id"].startswith("paddle-inference-3.3.0-")
    assert all(len(item["sha256"]) == 64 for item in lock["downloads"].values())
    assert "mklml.dll" in lock["runtime_files"]
    assert "vcomp140.dll" in lock["runtime_files"]
    patch = (ROOT / "native" / "knowledge_ocr" / "patches" / "paddleocr-v3.7.0-xenix.patch").read_text(
        encoding="utf-8"
    )
    assert "resize_long != pre_tfs.end()" in patch
    assert "stdout is reserved" in patch


def test_runtime_archive_is_deterministic_and_catalog_binds_exact_bytes(tmp_path: Path) -> None:
    build = _build_module()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "xenix-ocr.exe").write_bytes(b"worker")
    (runtime / "runtime.json").write_text("{}\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    build.write_deterministic_archive(runtime, first)
    build.write_deterministic_archive(runtime, second)

    assert first.read_bytes() == second.read_bytes()
    catalog = tmp_path / "runtime_catalog.json"
    lock = build.load_lock()
    build.write_catalog(lock, first, catalog)
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    assert payload["artifact_name"] == "first.zip"
    assert payload["artifact_bytes"] == first.stat().st_size
    assert payload["artifact_sha256"] == build.sha256_file(first)


def test_native_worker_source_owns_only_bounded_stdio_protocol() -> None:
    source = (ROOT / "native" / "knowledge_ocr" / "src" / "main.cpp").read_text(
        encoding="utf-8"
    )

    assert '"--stdio"' in source
    assert "kMaxMessageBytes" in source
    assert 'operation == "initialize"' in source
    assert 'operation == "recognize"' in source
    assert 'operation == "shutdown"' in source
    assert "sqlite" not in source.casefold()
    assert "http" not in source.casefold()


def test_vcomp_resolver_uses_visual_studio_installation_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    build = _build_module()
    program_files_x86 = tmp_path / "Program Files (x86)"
    vswhere = (
        program_files_x86
        / "Microsoft Visual Studio"
        / "Installer"
        / "vswhere.exe"
    )
    vswhere.parent.mkdir(parents=True)
    vswhere.write_bytes(b"vswhere")
    installation = tmp_path / "Program Files" / "Microsoft Visual Studio" / "2022" / "Enterprise"
    payload = b"locked vcomp runtime"
    vcomp = (
        installation
        / "VC"
        / "Redist"
        / "MSVC"
        / "14.44.35211.0"
        / "x64"
        / "Microsoft.VC143.OpenMP"
        / "vcomp140.dll"
    )
    vcomp.parent.mkdir(parents=True)
    vcomp.write_bytes(payload)
    toolchain = {
        "vcomp140_version": "14.44.35211.0",
        "vcomp140_bytes": len(payload),
        "vcomp140_sha256": hashlib.sha256(payload).hexdigest(),
    }

    class _Completed:
        returncode = 0
        stdout = str(installation)

    monkeypatch.setenv("ProgramFiles(x86)", str(program_files_x86))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty-program-files"))
    monkeypatch.setenv("SystemRoot", str(tmp_path / "empty-windows"))
    monkeypatch.setattr(build.subprocess, "run", lambda *_args, **_kwargs: _Completed())

    assert build._resolve_vcomp(None, toolchain) == vcomp.resolve()
