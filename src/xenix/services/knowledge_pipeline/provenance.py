"""Compute bounded pipeline fingerprints and report backend package versions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from ...exceptions import ValidationError


MAX_HASHABLE_IR_BYTES = 256 * 1024 * 1024
_HASH_CHUNK_BYTES = 1024 * 1024


def _sha256_file_bounded(
    path: Path,
    *,
    max_bytes: int,
) -> str:
    size = path.stat().st_size
    if size < 0 or size > max_bytes:
        raise ValidationError("Knowledge pipeline hash input exceeds the supported limit.")
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as source:
        while True:
            block = source.read(_HASH_CHUNK_BYTES)
            if not block:
                break
            consumed += len(block)
            if consumed > max_bytes:
                raise ValidationError(
                    "Knowledge pipeline hash input exceeds the supported limit."
                )
            digest.update(block)
    return digest.hexdigest()


def _runtime_package(name: str, version: str) -> dict[str, str]:
    return {"name": name, "version": version}


def _installed_package(distribution: str) -> dict[str, str]:
    try:
        installed_version = package_version(distribution)
    except PackageNotFoundError:
        installed_version = "unknown"
    return _runtime_package(distribution, installed_version)


def _bounded_json_sha256(
    value: Any,
    *,
    label: str,
    max_bytes: int = MAX_HASHABLE_IR_BYTES,
) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError(f"{label} cannot be hashed safely.") from exc
    if len(payload) > max_bytes:
        raise ValidationError(f"{label} exceeds the supported hash limit.")
    return hashlib.sha256(payload).hexdigest()


def _docling_document_sha256(document: Any) -> str:
    try:
        exported = document.export_to_dict()
    except Exception as exc:
        raise ValidationError("Docling content cannot be hashed safely.") from exc
    return _bounded_json_sha256(
        _redact_path_values_for_hash(exported),
        label="Docling content",
    )


def _redact_path_values_for_hash(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(item_key): _redact_path_values_for_hash(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_path_values_for_hash(item, key=key) for item in value]
    if isinstance(value, str) and key in {"path", "uri"}:
        candidate = Path(value)
        if candidate.is_absolute() or "://" in value or value.startswith(("~", "\\\\")):
            return "<redacted-path>"
    return value


def _combined_projection_sha256(payload_hashes: Iterable[tuple[int, str]]) -> str | None:
    ordered = [
        {"ordinal": ordinal, "sha256": payload_sha256}
        for ordinal, payload_sha256 in payload_hashes
    ]
    if not ordered:
        return None
    return _bounded_json_sha256(ordered, label="OCR projection hashes", max_bytes=64 * 1024)
