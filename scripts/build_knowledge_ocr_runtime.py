from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, BinaryIO, Literal, Self, cast
from uuid import uuid4
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError as PydanticValidationError,
    field_validator,
    model_validator,
)


ROOT = Path(__file__).resolve().parents[1]
NATIVE_ROOT = ROOT / "native" / "knowledge_ocr"
LOCK_PATH = NATIVE_ROOT / "runtime.lock.json"
DEFAULT_WORK_ROOT = ROOT / "build" / "knowledge-ocr"
DEFAULT_OUTPUT_ROOT = ROOT / "dist" / "knowledge-ocr"
MAX_PROTOCOL_MESSAGE_BYTES = 16 * 1024 * 1024
ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
RUNTIME_DIRECTORY = "xenix-knowledge-ocr"
REQUIRED_DOWNLOADS = {
    "paddle_inference",
    "opencv",
    "detection_model",
    "recognition_model",
    "abseil",
    "clipper",
    "nlohmann",
    "dirent",
    "golden_image",
}


def _content_addressed_artifact_name(runtime_id: str, artifact_sha256: str) -> str:
    return f"xenix-knowledge-ocr-win-x64-{runtime_id}-{artifact_sha256}.zip"


class _LockDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _validated_https_url(value: str) -> str:
    if value != value.strip():
        raise ValueError("URL must not contain surrounding whitespace.")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("URL must be absolute HTTPS.")
    return value


class PaddleOcrSourceLock(_LockDocument):
    repository: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")

    @field_validator("repository")
    @classmethod
    def _repository_must_be_https(cls, value: str) -> str:
        return _validated_https_url(value)


class DownloadLock(_LockDocument):
    url: str
    bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("url")
    @classmethod
    def _url_must_be_https(cls, value: str) -> str:
        return _validated_https_url(value)


class ToolchainLock(_LockDocument):
    cmake_minimum: str = Field(min_length=1)
    generator: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    vcomp140_version: str = Field(min_length=1)
    vcomp140_bytes: int = Field(gt=0)
    vcomp140_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator(
        "cmake_minimum",
        "generator",
        "architecture",
        "vcomp140_version",
    )
    @classmethod
    def _values_must_be_trimmed(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Toolchain values must not contain surrounding whitespace.")
        return value


class KnowledgeOcrRuntimeLock(_LockDocument):
    schema_version: Literal[1]
    protocol_version: Literal[2]
    runtime_id: str
    model_pack_id: str
    paddleocr: PaddleOcrSourceLock
    downloads: dict[str, DownloadLock]
    toolchain: ToolchainLock
    runtime_files: list[str]

    @field_validator("runtime_id", "model_pack_id")
    @classmethod
    def _identity_must_be_a_file_name(cls, value: str) -> str:
        if not value or value != value.strip() or Path(value).name != value:
            raise ValueError("Runtime identities must be non-empty file names.")
        return value

    @field_validator("downloads")
    @classmethod
    def _downloads_must_be_complete(
        cls,
        value: dict[str, DownloadLock],
    ) -> dict[str, DownloadLock]:
        if set(value) != REQUIRED_DOWNLOADS:
            raise ValueError("Required download closure is incomplete.")
        return value

    @model_validator(mode="after")
    def _runtime_files_must_be_complete(self) -> Self:
        if (
            not self.runtime_files
            or len(self.runtime_files) != len(set(self.runtime_files))
            or any(
                not name
                or name != name.strip()
                or name in {".", ".."}
                or Path(name).name != name
                for name in self.runtime_files
            )
        ):
            raise ValueError("Runtime files must be unique non-empty file names.")
        return self


class KnowledgeOcrRuntimeCatalog(_LockDocument):
    schema_version: Literal[1]
    artifact_name: str
    artifact_bytes: int = Field(gt=0)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol_version: Literal[2]
    runtime_id: str
    model_pack_id: str

    @field_validator("artifact_name")
    @classmethod
    def _artifact_name_must_be_safe(cls, value: str) -> str:
        if not value or value in {".", ".."} or Path(value).name != value:
            raise ValueError("Artifact name must be a safe file name.")
        return value

    @model_validator(mode="after")
    def _artifact_name_must_match_content_identity(self) -> Self:
        expected = _content_addressed_artifact_name(
            self.runtime_id,
            self.artifact_sha256,
        )
        if self.artifact_name != expected:
            raise ValueError(
                "Artifact name must include the runtime and content identities."
            )
        return self


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_lock(path: Path = LOCK_PATH) -> KnowledgeOcrRuntimeLock:
    try:
        lock = KnowledgeOcrRuntimeLock.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, PydanticValidationError) as exc:
        raise RuntimeError(f"Knowledge OCR runtime lock is invalid: {path}") from exc
    return lock


def download_locked(name: str, item: DownloadLock, cache: Path) -> Path:
    suffix = Path(urlparse(item.url).path).suffix or ".bin"
    target = cache / f"{name}{suffix}"
    cache.mkdir(parents=True, exist_ok=True)
    if _matches_lock(target, item):
        return target
    partial = target.with_name(f".{target.name}.{uuid4().hex}.part")
    try:
        with urllib.request.urlopen(item.url, timeout=120) as response, partial.open(
            "wb"
        ) as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if not _matches_lock(partial, item):
            raise RuntimeError(f"Downloaded Knowledge OCR input failed verification: {name}")
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def _matches_lock(path: Path, item: DownloadLock) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == item.bytes
        and sha256_file(path) == item.sha256
    )


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _visual_studio_installations() -> list[Path]:
    candidates: list[Path] = []
    vswhere = (
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Microsoft Visual Studio"
        / "Installer"
        / "vswhere.exe"
    )
    if vswhere.is_file():
        result = subprocess.run(
            [
                str(vswhere),
                "-all",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            candidates.extend(
                Path(line.strip())
                for line in result.stdout.splitlines()
                if line.strip()
            )
    for environment, default in (
        ("ProgramFiles", "C:/Program Files"),
        ("ProgramFiles(x86)", "C:/Program Files (x86)"),
    ):
        root = Path(os.environ.get(environment, default)) / "Microsoft Visual Studio"
        if root.is_dir():
            candidates.extend(
                path
                for path in root.glob("*/*")
                if path.is_dir() and path.name != "Installer"
            )
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen and resolved.is_dir():
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _resolve_cmake() -> str:
    configured = os.environ.get("XENIX_CMAKE", "").strip()
    if configured:
        path = Path(configured).resolve()
        if path.is_file():
            return str(path)
        raise RuntimeError("XENIX_CMAKE does not name an existing executable.")
    discovered = shutil.which("cmake")
    if discovered:
        return discovered
    for installation in _visual_studio_installations():
        candidate = (
            installation
            / "Common7"
            / "IDE"
            / "CommonExtensions"
            / "Microsoft"
            / "CMake"
            / "CMake"
            / "bin"
            / "cmake.exe"
        )
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("CMake was not found; install the Visual Studio C++ CMake tools.")


def _prepare_source(lock: KnowledgeOcrRuntimeLock, source: Path) -> Path:
    expected_commit = lock.paddleocr.commit
    if not source.exists():
        _run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                lock.paddleocr.repository,
                str(source),
            ]
        )
    _run(["git", "fetch", "--depth=1", "origin", expected_commit], cwd=source)
    _run(["git", "checkout", "--detach", expected_commit], cwd=source)
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual != expected_commit:
        raise RuntimeError("PaddleOCR source commit does not match the runtime lock.")
    patch = NATIVE_ROOT / "patches" / "paddleocr-v3.7.0-xenix.patch"
    check = subprocess.run(
        ["git", "apply", "--check", str(patch)],
        cwd=source,
        capture_output=True,
    )
    if check.returncode == 0:
        _run(["git", "apply", str(patch)], cwd=source)
    elif subprocess.run(
        ["git", "apply", "--reverse", "--check", str(patch)],
        cwd=source,
        capture_output=True,
    ).returncode != 0:
        raise RuntimeError("The pinned PaddleOCR compatibility patch cannot be applied.")
    return source


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as package:
        for member in package.getmembers():
            target = (destination / member.name).resolve()
            target.relative_to(destination.resolve())
            if member.issym() or member.islnk():
                raise RuntimeError("Knowledge OCR input archive contains a link.")
        package.extractall(destination, filter="data")


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            target.relative_to(destination.resolve())
        package.extractall(destination)


def _single_directory(root: Path) -> Path:
    entries = [path for path in root.iterdir() if path.name != "__MACOSX"]
    if len(entries) != 1 or not entries[0].is_dir():
        raise RuntimeError(f"Expected one extracted directory under {root}.")
    return entries[0]


def _source_tree(root: Path) -> Path:
    """Accept dependency archives that are either rooted or flat."""

    entries = [path for path in root.iterdir() if path.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    if entries:
        return root
    raise RuntimeError(f"Expected a source tree under {root}.")


def _extract_inputs(
    downloads: dict[str, Path],
    work: Path,
    source: Path,
) -> tuple[Path, Path, Path, Path]:
    extracted = work / "extracted"
    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True)

    paddle_stage = extracted / "paddle"
    _safe_extract_zip(downloads["paddle_inference"], paddle_stage)
    paddle_root = next(
        path.parent.parent.parent
        for path in paddle_stage.rglob("paddle/include/paddle_inference_api.h")
    )

    opencv_stage = extracted / "opencv"
    opencv_stage.mkdir()
    _run([str(downloads["opencv"]), f"-o{opencv_stage}", "-y"])
    opencv_root = next(
        path.parent.parent.parent.parent
        for path in opencv_stage.rglob("x64/vc16/lib/OpenCVConfig.cmake")
    )

    model_stage = extracted / "models"
    detection_stage = model_stage / "detection"
    recognition_stage = model_stage / "recognition"
    _safe_extract_tar(downloads["detection_model"], detection_stage)
    _safe_extract_tar(downloads["recognition_model"], recognition_stage)
    detection_model = _single_directory(detection_stage)
    recognition_model = _single_directory(recognition_stage)

    cpp_root = source / "deploy" / "cpp_infer"
    third_party = cpp_root / "third_party"
    for download_name, directory_name in (
        ("abseil", "abseil-cpp"),
        ("clipper", "clipper_ver6.4.2"),
        ("nlohmann", "nlohmann"),
    ):
        target = third_party / directory_name
        if target.exists():
            shutil.rmtree(target)
        temporary = extracted / f"third-party-{download_name}"
        _safe_extract_tar(downloads[download_name], temporary)
        shutil.copytree(_source_tree(temporary), target)
    shutil.copy2(downloads["dirent"], cpp_root / "dirent.h")
    return paddle_root, opencv_root, detection_model, recognition_model


def _build_worker(
    lock: KnowledgeOcrRuntimeLock,
    *,
    work: Path,
    source: Path,
    paddle_root: Path,
    opencv_root: Path,
) -> Path:
    build = work / "cmake"
    if build.exists():
        shutil.rmtree(build)
    toolchain = lock.toolchain
    cmake = _resolve_cmake()
    _run(
        [
            cmake,
            "-S",
            str(NATIVE_ROOT),
            "-B",
            str(build),
            "-G",
            toolchain.generator,
            "-A",
            toolchain.architecture,
            f"-DXENIX_PADDLEOCR_SOURCE={source}",
            f"-DPADDLE_LIB={paddle_root}",
            f"-DOPENCV_DIR={opencv_root}",
            "-DWITH_GPU=OFF",
            "-DWITH_MKL=ON",
            # Upstream's Windows shared branch links the .dll itself. Its
            # "static" branch correctly selects Paddle's import .lib while
            # the resulting worker still loads the pinned runtime DLLs.
            "-DWITH_STATIC_LIB=ON",
            # Clipper sets this cache variable too late for Abseil during a
            # first clean configure. Set it up front so Abseil builds the one
            # DLL that PaddleOCR's target graph expects on Windows.
            "-DBUILD_SHARED_LIBS=ON",
            "-DUSE_FREETYPE=OFF",
        ]
    )
    _run([cmake, "--build", str(build), "--config", "Release", "--target", "ppocr"])
    candidates = list(build.rglob("xenix-ocr.exe"))
    if len(candidates) != 1:
        raise RuntimeError("The native OCR build did not produce exactly one worker.")
    return candidates[0]


def _find_unique(root: Path, name: str) -> Path:
    candidates = [path for path in root.rglob(name) if path.is_file()]
    if not candidates:
        raise RuntimeError(f"Required native OCR dependency is missing: {name}")
    candidates.sort(key=lambda path: (len(path.parts), str(path)))
    return candidates[0]


def _verify_vcomp(path: Path, toolchain: ToolchainLock) -> None:
    if (
        path.stat().st_size != toolchain.vcomp140_bytes
        or sha256_file(path) != toolchain.vcomp140_sha256
    ):
        raise RuntimeError(
            "vcomp140.dll does not match the pinned MSVC redistributable; "
            "set --vcomp140 to the exact locked file."
        )


def _resolve_vcomp(
    configured: Path | None,
    toolchain: ToolchainLock,
) -> Path:
    candidates: list[Path] = []
    if configured is not None:
        candidates.append(configured.resolve())
    environment = os.environ.get("XENIX_VCOMP140_PATH", "").strip()
    if environment:
        candidates.append(Path(environment).resolve())
    for installation in _visual_studio_installations():
        redist = installation / "VC" / "Redist" / "MSVC"
        locked = (
            redist
            / toolchain.vcomp140_version
            / "x64"
            / "Microsoft.VC143.OpenMP"
            / "vcomp140.dll"
        )
        candidates.append(locked)
        if redist.is_dir():
            candidates.extend(
                sorted(
                    redist.glob("*/x64/Microsoft.VC143.OpenMP/vcomp140.dll"),
                    reverse=True,
                )
            )
    system_root = Path(os.environ.get("SystemRoot", "C:/Windows"))
    candidates.append(system_root / "System32" / "vcomp140.dll")
    checked: set[Path] = set()
    for candidate in candidates:
        if candidate in checked or not candidate.is_file():
            continue
        checked.add(candidate)
        try:
            _verify_vcomp(candidate, toolchain)
        except RuntimeError:
            continue
        return candidate
    raise RuntimeError(
        "The exact locked vcomp140.dll was not found; pass --vcomp140 or set "
        "XENIX_VCOMP140_PATH."
    )


def _stage_runtime(
    lock: KnowledgeOcrRuntimeLock,
    *,
    work: Path,
    worker: Path,
    paddle_root: Path,
    opencv_root: Path,
    detection_model: Path,
    recognition_model: Path,
    vcomp140: Path,
) -> Path:
    stage_parent = work / "stage"
    if stage_parent.exists():
        shutil.rmtree(stage_parent)
    runtime = stage_parent / RUNTIME_DIRECTORY
    runtime.mkdir(parents=True)
    build_root = work / "cmake"
    dependency_roots = [build_root, paddle_root, opencv_root]
    for name in lock.runtime_files:
        source: Path | None
        if name == "xenix-ocr.exe":
            source = worker
        elif name == "vcomp140.dll":
            _verify_vcomp(vcomp140, lock.toolchain)
            source = vcomp140
        else:
            source = next(
                (_find_unique(root, name) for root in dependency_roots if list(root.rglob(name))),
                None,
            )
            if source is None:
                raise RuntimeError(f"Required native OCR dependency is missing: {name}")
        shutil.copy2(source, runtime / name)

    models = runtime / "models"
    shutil.copytree(detection_model, models / "PP-OCRv6_medium_det")
    shutil.copytree(recognition_model, models / "PP-OCRv6_medium_rec")
    shutil.copy2(NATIVE_ROOT / "THIRD_PARTY_NOTICES.txt", runtime)

    licenses = runtime / "licenses"
    licenses.mkdir()
    paddle_license = _find_unique(
        work / "PaddleOCR", "LICENSE"
    )
    shutil.copy2(paddle_license, licenses / "PaddleOCR-LICENSE.txt")
    shutil.copy2(paddle_license, licenses / "Paddle-Inference-LICENSE.txt")
    shutil.copy2(_find_unique(opencv_root, "LICENSE"), licenses / "OpenCV-LICENSE.txt")
    shutil.copy2(
        _find_unique(work / "PaddleOCR" / "deploy" / "cpp_infer" / "third_party" / "abseil-cpp", "LICENSE"),
        licenses / "Abseil-LICENSE.txt",
    )
    shutil.copy2(
        _find_unique(work / "PaddleOCR" / "deploy" / "cpp_infer" / "third_party" / "nlohmann", "LICENSE.MIT"),
        licenses / "nlohmann-json-LICENSE.txt",
    )

    files = [_file_entry(path, runtime) for path in sorted(runtime.rglob("*")) if path.is_file()]
    manifest = {
        "schema_version": 1,
        "protocol_version": lock.protocol_version,
        "runtime_id": lock.runtime_id,
        "model_pack_id": lock.model_pack_id,
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
    (runtime / "runtime.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return runtime


def _file_entry(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _write_frame(stream: BinaryIO, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack(">I", len(encoded)))
    stream.write(encoded)
    stream.flush()


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        chunk = stream.read(size - len(result))
        if not chunk:
            raise RuntimeError("Native OCR worker closed its protocol stream.")
        result.extend(chunk)
    return bytes(result)


def _read_frame(stream: BinaryIO) -> dict[str, Any]:
    size = struct.unpack(">I", _read_exact(stream, 4))[0]
    if size < 2 or size > MAX_PROTOCOL_MESSAGE_BYTES:
        raise RuntimeError("Native OCR protocol response is outside its bound.")
    value = json.loads(_read_exact(stream, size))
    if not isinstance(value, dict):
        raise RuntimeError("Native OCR protocol response is not an object.")
    return value


def _request(
    process: subprocess.Popen[bytes],
    request_id: str,
    operation: str,
    arguments: dict[str, object],
) -> Any:
    assert process.stdin is not None and process.stdout is not None
    _write_frame(
        cast(BinaryIO, process.stdin),
        {
            "protocol_version": 2,
            "request_id": request_id,
            "operation": operation,
            "arguments": arguments,
        },
    )
    response = _read_frame(cast(BinaryIO, process.stdout))
    if response.get("request_id") != request_id or response.get("ok") is not True:
        raise RuntimeError(f"Native OCR protocol request failed: {operation}")
    return response.get("result")


def verify_runtime(runtime: Path, golden_image: Path) -> None:
    log = runtime / "build-verification.log"
    with log.open("wb") as stderr:
        process = subprocess.Popen(
            [str(runtime / "xenix-ocr.exe"), "--stdio"],
            cwd=runtime,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
        )
        try:
            version = _request(process, "version", "version", {})
            if version.get("runtime_id") != "paddle-inference-3.3.0-paddleocr-3.7.0-win-x64":
                raise RuntimeError("Native OCR runtime identity is invalid.")
            initialized = _request(
                process,
                "initialize",
                "initialize",
                {
                    "model_pack_id": "pp-ocrv6-medium-zh-en-1",
                    "detection_model_path": str(runtime / "models" / "PP-OCRv6_medium_det"),
                    "recognition_model_path": str(runtime / "models" / "PP-OCRv6_medium_rec"),
                },
            )
            if initialized != {"initialized": True}:
                raise RuntimeError("Native OCR initialization failed.")
            _request(process, "self-test", "self_test", {})
            for index in range(10):
                result = _request(
                    process,
                    f"recognize-{index}",
                    "recognize",
                    {"image_path": str(golden_image.resolve())},
                )
                text = "\n".join(str(region.get("text", "")) for region in result["regions"])
                if "登机牌" not in text or "BOARDING" not in text:
                    raise RuntimeError("Native OCR golden result is incompatible.")
            _request(process, "shutdown", "shutdown", {})
            if process.wait(timeout=10) != 0:
                raise RuntimeError("Native OCR worker did not shut down cleanly.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    log.unlink(missing_ok=True)


def write_content_addressed_archive(
    runtime: Path,
    output: Path,
    *,
    runtime_id: str,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / f".knowledge-ocr-{uuid4().hex}.zip"
    try:
        with zipfile.ZipFile(
            temporary,
            "x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as package:
            for path in sorted(runtime.rglob("*")):
                if not path.is_file():
                    continue
                relative = Path(RUNTIME_DIRECTORY) / path.relative_to(runtime)
                info = zipfile.ZipInfo(relative.as_posix(), ARCHIVE_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                package.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        artifact_sha256 = sha256_file(temporary)
        destination = output / _content_addressed_artifact_name(
            runtime_id,
            artifact_sha256,
        )
        if destination.exists():
            if sha256_file(destination) != artifact_sha256:
                raise RuntimeError(
                    "Knowledge OCR content-addressed artifact conflicts with existing output."
                )
        else:
            os.replace(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def write_catalog(
    lock: KnowledgeOcrRuntimeLock,
    archive: Path,
    destination: Path,
) -> None:
    payload = KnowledgeOcrRuntimeCatalog(
        schema_version=1,
        artifact_name=archive.name,
        artifact_bytes=archive.stat().st_size,
        artifact_sha256=sha256_file(archive),
        protocol_version=lock.protocol_version,
        runtime_id=lock.runtime_id,
        model_pack_id=lock.model_pack_id,
    )
    destination.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_output(args: argparse.Namespace) -> tuple[Path, Path]:
    lock = load_lock()
    output = args.output_dir.resolve()
    cache = args.cache_dir.resolve()
    catalog = output / "runtime_catalog.json"
    if not catalog.is_file():
        raise RuntimeError("Cached Knowledge OCR runtime catalog is missing.")
    try:
        payload = KnowledgeOcrRuntimeCatalog.model_validate_json(
            catalog.read_text(encoding="utf-8")
        )
    except (OSError, PydanticValidationError) as exc:
        raise RuntimeError("Cached Knowledge OCR runtime catalog is invalid.") from exc
    if (
        payload.protocol_version != lock.protocol_version
        or payload.runtime_id != lock.runtime_id
        or payload.model_pack_id != lock.model_pack_id
    ):
        raise RuntimeError("Cached Knowledge OCR runtime identity is invalid.")
    archive = output / payload.artifact_name
    if (
        not archive.is_file()
        or archive.stat().st_size != payload.artifact_bytes
        or sha256_file(archive) != payload.artifact_sha256
    ):
        raise RuntimeError("Cached Knowledge OCR runtime artifact is corrupt.")

    golden = download_locked("golden_image", lock.downloads["golden_image"], cache)
    verification = args.work_dir.resolve() / "cached-output-verification"
    shutil.rmtree(verification, ignore_errors=True)
    try:
        _safe_extract_zip(archive, verification)
        runtime = verification / RUNTIME_DIRECTORY
        if not runtime.is_dir():
            raise RuntimeError("Cached Knowledge OCR archive layout is invalid.")
        verify_runtime(runtime, golden)
    finally:
        shutil.rmtree(verification, ignore_errors=True)
    return archive, catalog


def build(args: argparse.Namespace) -> tuple[Path, Path]:
    lock = load_lock()
    work = args.work_dir.resolve()
    output = args.output_dir.resolve()
    cache = args.cache_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    downloads = {
        name: download_locked(name, item, cache)
        for name, item in lock.downloads.items()
    }
    source = _prepare_source(lock, work / "PaddleOCR")
    paddle, opencv, detection, recognition = _extract_inputs(downloads, work, source)
    worker = _build_worker(
        lock,
        work=work,
        source=source,
        paddle_root=paddle,
        opencv_root=opencv,
    )
    vcomp = _resolve_vcomp(args.vcomp140, lock.toolchain)
    runtime = _stage_runtime(
        lock,
        work=work,
        worker=worker,
        paddle_root=paddle,
        opencv_root=opencv,
        detection_model=detection,
        recognition_model=recognition,
        vcomp140=vcomp,
    )
    verify_runtime(runtime, downloads["golden_image"])
    archive = write_content_addressed_archive(
        runtime,
        output,
        runtime_id=lock.runtime_id,
    )
    catalog = output / "runtime_catalog.json"
    write_catalog(lock, archive, catalog)
    return archive, catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the pinned Xenix native OCR runtime")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_WORK_ROOT / "downloads")
    parser.add_argument("--vcomp140", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify-output",
        action="store_true",
        help="Verify a cached output archive, including its native OCR self-test.",
    )
    mode.add_argument(
        "--check-lock",
        action="store_true",
        help="Validate the pinned lock without downloading or building the runtime.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_lock:
        load_lock()
        print(f"Knowledge OCR lock is valid: {LOCK_PATH}")
        return 0
    archive, catalog = verify_output(args) if args.verify_output else build(args)
    print(archive)
    print(catalog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
