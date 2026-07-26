from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_knowledge_ocr_runtime.py"


def _build_module():
    spec = importlib.util.spec_from_file_location("xenix_ocr_build_for_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_cached_runtime_restore_revalidates_archive_and_native_self_test(
    monkeypatch,
    tmp_path: Path,
) -> None:
    build = _build_module()
    output = tmp_path / "output"
    output.mkdir()
    staged_runtime = tmp_path / "runtime"
    staged_runtime.mkdir()
    (staged_runtime / "xenix-ocr.exe").write_bytes(b"worker")
    archive = output / "xenix-knowledge-ocr.zip"
    build.write_deterministic_archive(staged_runtime, archive)
    build.write_catalog(build.load_lock(), archive, output / "runtime_catalog.json")
    golden = tmp_path / "golden.png"
    golden.write_bytes(b"image")
    verified: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        build,
        "download_locked",
        lambda *_args, **_kwargs: golden,
    )
    monkeypatch.setattr(
        build,
        "verify_runtime",
        lambda runtime, image: verified.append((runtime, image)),
    )

    restored_archive, catalog = build.verify_output(
        SimpleNamespace(
            output_dir=output,
            cache_dir=tmp_path / "downloads",
            work_dir=tmp_path / "work",
        )
    )

    assert restored_archive == archive
    assert catalog == output / "runtime_catalog.json"
    assert len(verified) == 1
    assert verified[0][0].name == build.RUNTIME_DIRECTORY
    assert verified[0][1] == golden


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
    toolchain = build.ToolchainLock(
        cmake_minimum="3.24",
        generator="Visual Studio 17 2022",
        architecture="x64",
        vcomp140_version="14.44.35211.0",
        vcomp140_bytes=len(payload),
        vcomp140_sha256=hashlib.sha256(payload).hexdigest(),
    )

    class _Completed:
        returncode = 0
        stdout = str(installation)

    monkeypatch.setenv("ProgramFiles(x86)", str(program_files_x86))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty-program-files"))
    monkeypatch.setenv("SystemRoot", str(tmp_path / "empty-windows"))
    monkeypatch.setattr(build.subprocess, "run", lambda *_args, **_kwargs: _Completed())

    assert build._resolve_vcomp(None, toolchain) == vcomp.resolve()
