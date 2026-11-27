from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from zipfile import ZipFile, ZipInfo

from ...config import package_root
from ...exceptions import ValidationError
from ...release_config import ReleaseConfig
from .contracts import (
    CATALOG_OVERRIDE_ENV,
    CATALOG_RESOURCE_NAME,
    LOCAL_ARTIFACT_OVERRIDE_ENV,
    NATIVE_OCR_PROTOCOL_VERSION,
    RUNTIME_MANIFEST_NAME,
    RUNTIME_MANIFEST_SCHEMA_VERSION,
    PaddleOcrBundleCatalog,
    bounded_identity,
    bounded_json_file,
    positive_int,
    relative_member,
    resolve_member,
    sha256_file,
    sha256_text,
)


class PaddleOcrBundleSource(Protocol):
    """Catalog authority plus one way to materialize its exact archive."""

    @property
    def catalog(self) -> PaddleOcrBundleCatalog: ...

    def ensure_available(self) -> None:
        """Fail with a safe typed error when this source cannot provide its archive."""

    def materialize(self, destination: Path) -> None:
        """Write the source artifact to one private destination."""


@dataclass(frozen=True)
class LocalPaddleOcrBundleSource:
    """A development or smoke archive paired with its generated catalog."""

    catalog: PaddleOcrBundleCatalog
    artifact_path: Path

    def ensure_available(self) -> None:
        source = self.artifact_path
        if source.name != self.catalog.artifact_name:
            raise ValidationError(
                "Local OCR bundle does not match its catalog.",
                error_code="knowledge_ocr_bundle_source_mismatch",
            )
        if not source.is_file():
            raise ValidationError(
                "Local OCR bundle is unavailable.",
                error_code="knowledge_ocr_bundle_source_unavailable",
            )

    def materialize(self, destination: Path) -> None:
        source = self.artifact_path
        self.ensure_available()
        try:
            with source.open("rb") as input_stream, destination.open("wb") as output:
                shutil.copyfileobj(input_stream, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
        except OSError as exc:
            destination.unlink(missing_ok=True)
            raise ValidationError(
                "Local OCR bundle is unavailable.",
                error_code="knowledge_ocr_bundle_source_unavailable",
            ) from exc


@dataclass(frozen=True)
class ReleasePaddleOcrBundleSource:
    """A catalog-owned archive resolved through the immutable release origin."""

    catalog: PaddleOcrBundleCatalog
    release_config: ReleaseConfig

    def _artifact_url(self) -> str:
        artifact_url = self.release_config.artifact_url(self.catalog.artifact_name)
        if not artifact_url:
            raise ValidationError(
                "Local OCR download is unavailable in this build.",
                error_code="knowledge_ocr_download_unavailable",
            )
        return artifact_url

    def ensure_available(self) -> None:
        self._artifact_url()

    def materialize(self, destination: Path) -> None:
        artifact_url = self._artifact_url()
        try:
            with urllib.request.urlopen(artifact_url, timeout=120) as response, destination.open(
                "wb"
            ) as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
        except OSError as exc:
            destination.unlink(missing_ok=True)
            raise ValidationError(
                "Local OCR component could not be downloaded.",
                error_code="knowledge_ocr_download_failed",
            ) from exc


def load_default_bundle_source(
    release_config: ReleaseConfig,
) -> PaddleOcrBundleSource | None:
    catalog = load_packaged_catalog()
    if catalog is None:
        return None
    artifact_override = os.environ.get(LOCAL_ARTIFACT_OVERRIDE_ENV, "").strip()
    if artifact_override:
        return LocalPaddleOcrBundleSource(catalog, Path(artifact_override))
    return ReleasePaddleOcrBundleSource(catalog, release_config)


def load_packaged_catalog() -> PaddleOcrBundleCatalog | None:
    override = os.environ.get(CATALOG_OVERRIDE_ENV, "").strip()
    path = Path(override) if override else package_root() / "resources" / "knowledge_ocr" / CATALOG_RESOURCE_NAME
    if not path.is_file():
        return None
    try:
        return PaddleOcrBundleCatalog.from_payload(bounded_json_file(path))
    except (OSError, TypeError, ValueError):
        return None


def matches_catalog_artifact(path: Path, catalog: PaddleOcrBundleCatalog) -> bool:
    try:
        return (
            path.is_file()
            and path.stat().st_size == catalog.artifact_bytes
            and sha256_file(path) == catalog.artifact_sha256
        )
    except OSError:
        return False


def validate_runtime_manifest(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.keys() != {
        "schema_version",
        "protocol_version",
        "runtime_id",
        "model_pack_id",
        "engine",
        "engine_version",
        "architecture",
        "executable",
        "models",
        "files",
    }:
        raise ValueError("Native OCR runtime manifest shape is invalid.")
    if payload.get("schema_version") != RUNTIME_MANIFEST_SCHEMA_VERSION:
        raise ValueError("Native OCR runtime manifest schema is incompatible.")
    if payload.get("protocol_version") != NATIVE_OCR_PROTOCOL_VERSION:
        raise ValueError("Native OCR runtime protocol is incompatible.")
    if payload.get("engine") != "paddle-inference" or payload.get("architecture") != "windows-x86_64":
        raise ValueError("Native OCR runtime identity is incompatible.")
    bounded_identity(payload.get("runtime_id"))
    bounded_identity(payload.get("model_pack_id"))
    bounded_identity(payload.get("engine_version"))
    relative_member(payload.get("executable"))
    models = payload.get("models")
    if not isinstance(models, dict) or models.keys() != {"detection", "recognition"}:
        raise ValueError("Native OCR model manifest is invalid.")
    relative_member(models.get("detection"))
    relative_member(models.get("recognition"))
    files = payload.get("files")
    if not isinstance(files, list) or not files or len(files) > 512:
        raise ValueError("Native OCR file manifest is invalid.")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or item.keys() != {"path", "bytes", "sha256"}:
            raise ValueError("Native OCR file manifest entry is invalid.")
        relative = relative_member(item.get("path"))
        if relative == RUNTIME_MANIFEST_NAME or relative in seen:
            raise ValueError("Native OCR file manifest contains a duplicate.")
        seen.add(relative)
        positive_int(item.get("bytes"), allow_zero=True)
        sha256_text(item.get("sha256"))
    if str(payload["executable"]) not in seen:
        raise ValueError("Native OCR executable is absent from the file manifest.")
    for model_path in models.values():
        prefix = f"{model_path.rstrip('/')}/"
        if not any(path.startswith(prefix) for path in seen):
            raise ValueError("Native OCR model files are absent from the manifest.")
    return payload


def verify_runtime_files(root: Path, manifest: dict[str, object]) -> None:
    expected = {RUNTIME_MANIFEST_NAME}
    files = manifest["files"]
    if not isinstance(files, list):
        raise ValueError("Native OCR runtime manifest file list is invalid.")
    for item in files:
        relative = str(item["path"])
        path = resolve_member(root, relative)
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != item["bytes"]
            or sha256_file(path) != item["sha256"]
        ):
            raise ValueError("Native OCR runtime file integrity check failed.")
        expected.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ValueError("Native OCR runtime contains unexpected files.")


def safe_extract_zip(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with ZipFile(archive) as package:
        if len(package.infolist()) > 1024:
            raise ValidationError(
                "Downloaded local OCR bundle contains too many entries.",
                error_code="knowledge_ocr_bundle_invalid",
            )
        for member in package.infolist():
            _validate_zip_member(member)
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValidationError(
                    "Downloaded local OCR bundle contains an unsafe path.",
                    error_code="knowledge_ocr_bundle_invalid",
                ) from exc
        package.extractall(destination)


def _validate_zip_member(member: ZipInfo) -> None:
    relative_member(member.filename.rstrip("/"))
    unix_mode = member.external_attr >> 16
    if unix_mode and (unix_mode & 0o170000) == 0o120000:
        raise ValidationError(
            "Downloaded local OCR bundle contains a symbolic link.",
            error_code="knowledge_ocr_bundle_invalid",
        )


def single_bundle_root(extracted: Path) -> Path:
    entries = list(extracted.iterdir())
    if len(entries) != 1 or not entries[0].is_dir() or entries[0].is_symlink():
        raise ValueError("Native OCR archive must contain one bundle directory.")
    return entries[0]


def generation_id(catalog: PaddleOcrBundleCatalog) -> str:
    identity = json.dumps(
        {
            "schema_version": 1,
            "runtime_id": catalog.runtime_id,
            "model_pack_id": catalog.model_pack_id,
            "artifact_sha256": catalog.artifact_sha256,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return f"ocr-{hashlib.sha256(identity).hexdigest()[:32]}"


def remove_private_tree(path: Path, *, root: Path) -> None:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    if resolved == root.resolve():
        raise ValueError("Refusing to remove the native OCR root.")
    shutil.rmtree(resolved)
