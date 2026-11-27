from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import uuid4

NATIVE_OCR_PROTOCOL_VERSION = 2
RUNTIME_MANIFEST_SCHEMA_VERSION = 1
BUNDLE_CATALOG_SCHEMA_VERSION = 1
MAX_STATUS_BYTES = 64 * 1024
MAX_PROTOCOL_MESSAGE_BYTES = 16 * 1024 * 1024
PROTOCOL_POLL_INTERVAL_SECONDS = 0.05
PROCESS_TERMINATE_GRACE_SECONDS = 1.0

RUNTIME_MANIFEST_NAME = "runtime.json"
ACTIVE_MANIFEST_NAME = "active.json"
VERIFICATION_RECORD_NAME = "verification.json"
CATALOG_RESOURCE_NAME = "runtime_catalog.json"
VERIFICATION_SCHEMA_VERSION = 1
VERIFICATION_MAX_AGE_SECONDS = 24 * 60 * 60
CATALOG_OVERRIDE_ENV = "XENIX_KNOWLEDGE_OCR_CATALOG"
LOCAL_ARTIFACT_OVERRIDE_ENV = "XENIX_KNOWLEDGE_OCR_ARTIFACT"
_SHA256_CHARS = frozenset("0123456789abcdef")


class PaddleOcrState(StrEnum):
    CHECKING = "checking"
    READY = "ready"
    NOT_INSTALLED = "not_installed"
    REPAIR_REQUIRED = "repair_required"
    INSTALLING = "installing"
    FAILED = "failed"


@dataclass(frozen=True)
class PaddleOcrStatus:
    state: PaddleOcrState
    reason_code: str | None = None
    runtime_id: str | None = None
    model_pack_id: str | None = None
    generation_id: int | None = None


@dataclass(frozen=True)
class PaddleOcrBundleCatalog:
    artifact_name: str
    artifact_bytes: int
    artifact_sha256: str
    protocol_version: int
    runtime_id: str
    model_pack_id: str

    @classmethod
    def from_payload(cls, payload: object) -> PaddleOcrBundleCatalog:
        if not isinstance(payload, dict) or payload.keys() != {
            "schema_version",
            "artifact_name",
            "artifact_bytes",
            "artifact_sha256",
            "protocol_version",
            "runtime_id",
            "model_pack_id",
        }:
            raise ValueError("Native OCR catalog shape is invalid.")
        if payload.get("schema_version") != BUNDLE_CATALOG_SCHEMA_VERSION:
            raise ValueError("Native OCR catalog schema is incompatible.")
        artifact_name = safe_file_name(payload.get("artifact_name"))
        artifact_bytes = positive_int(payload.get("artifact_bytes"))
        artifact_sha256 = sha256_text(payload.get("artifact_sha256"))
        protocol_version = positive_int(payload.get("protocol_version"))
        if protocol_version != NATIVE_OCR_PROTOCOL_VERSION:
            raise ValueError("Native OCR protocol is incompatible.")
        runtime_id = bounded_identity(payload.get("runtime_id"))
        model_pack_id = bounded_identity(payload.get("model_pack_id"))
        return cls(
            artifact_name=artifact_name,
            artifact_bytes=artifact_bytes,
            artifact_sha256=artifact_sha256,
            protocol_version=protocol_version,
            runtime_id=runtime_id,
            model_pack_id=model_pack_id,
        )


@dataclass(frozen=True)
class PaddleOcrRuntimeDescriptor:
    generation_id: int
    runtime_id: str
    model_pack_id: str
    engine: str
    engine_version: str
    protocol_version: int
    manifest_sha256: str

    def to_payload(self) -> dict[str, object]:
        return {
            "generation_id": self.generation_id,
            "runtime_id": self.runtime_id,
            "model_pack_id": self.model_pack_id,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "protocol_version": self.protocol_version,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True)
class PaddleOcrRuntime:
    generation_id: int
    generation_path: Path
    executable_path: Path
    detection_model_path: Path
    recognition_model_path: Path
    runtime_id: str
    model_pack_id: str
    engine_version: str
    manifest_sha256: str

    @property
    def descriptor(self) -> PaddleOcrRuntimeDescriptor:
        return PaddleOcrRuntimeDescriptor(
            generation_id=self.generation_id,
            runtime_id=self.runtime_id,
            model_pack_id=self.model_pack_id,
            engine="paddle-inference",
            engine_version=self.engine_version,
            protocol_version=NATIVE_OCR_PROTOCOL_VERSION,
            manifest_sha256=self.manifest_sha256,
        )


def bounded_json_file(path: Path, *, max_bytes: int = MAX_STATUS_BYTES) -> object:
    with path.open("rb") as source:
        raw = source.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("JSON file is outside the supported bound.")
    return bounded_json_object(raw.decode("utf-8"), max_bytes=max_bytes)


def bounded_json_object(raw: object, *, max_bytes: int) -> object:
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > max_bytes:
        raise ValueError("JSON payload is outside the supported bound.")

    def reject_constant(value: str) -> None:
        raise ValueError(f"Unsupported JSON constant: {value}")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON keys are unsupported.")
            result[key] = value
        return result

    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(payload, output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def resolve_member(root: Path, value: object) -> Path:
    relative = relative_member(value)
    target = (root / Path(*PurePosixPath(relative).parts)).resolve()
    target.relative_to(root.resolve())
    return target


def relative_member(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or "\\" in value:
        raise ValueError("Native OCR member path is invalid.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Native OCR member path is invalid.")
    return path.as_posix()


def safe_file_name(value: object) -> str:
    name = bounded_identity(value)
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Native OCR artifact name is invalid.")
    return name


def bounded_identity(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Native OCR identity is invalid.")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 160 or any(ord(char) < 0x20 for char in cleaned):
        raise ValueError("Native OCR identity is invalid.")
    return cleaned


def positive_int(value: object, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        raise ValueError("Native OCR numeric value is invalid.")
    return value


def sha256_text(value: object) -> str:
    if not is_sha256(value):
        raise ValueError("Native OCR digest is invalid.")
    return str(value)


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _SHA256_CHARS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
