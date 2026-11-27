from __future__ import annotations

import json
import math
import os
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from .contracts import (
    GENERATION_ID_PATTERN,
    MANIFEST_FILE_NAME,
    MANIFEST_KEYS,
    MANIFEST_SCHEMA_VERSION,
    MAX_FINGERPRINT_CHARACTERS,
    MAX_MANIFEST_BYTES,
    SHA256_PATTERN,
    KnowledgeVectorRecord,
    KnowledgeVectorStoreError,
)
from .filesystem import assert_within, is_link_like


def validate_generation_id(value: int | str) -> None:
    if not GENERATION_ID_PATTERN.fullmatch(str(value)):
        raise KnowledgeVectorStoreError()


def validated_fingerprint(value: str) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= MAX_FINGERPRINT_CHARACTERS
        or any(
            ord(character) < 0x21 or ord(character) > 0x7E
            for character in value
        )
    ):
        raise KnowledgeVectorStoreError()
    return value


def validated_positive_int(value: int) -> int:
    if type(value) is not int or value < 1:
        raise KnowledgeVectorStoreError()
    return value


def validated_unit_ids(values: Sequence[int]) -> list[int]:
    if isinstance(values, (str, bytes)):
        raise KnowledgeVectorStoreError()
    normalized: list[int] = []
    seen: set[int] = set()
    for value in values:
        unit_id = value
        if type(unit_id) is not int or unit_id < 1 or unit_id in seen:
            raise KnowledgeVectorStoreError()
        seen.add(unit_id)
        normalized.append(unit_id)
    if not normalized:
        raise KnowledgeVectorStoreError()
    return normalized


def validated_vector(values: Sequence[float]) -> tuple[float, ...]:
    try:
        vector = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise KnowledgeVectorStoreError() from exc
    if not vector or not all(math.isfinite(value) for value in vector):
        raise KnowledgeVectorStoreError()
    return vector


def validated_records(
    records: Sequence[KnowledgeVectorRecord],
    *,
    dimensions: int,
) -> list[KnowledgeVectorRecord]:
    if dimensions < 1 or not records:
        raise KnowledgeVectorStoreError()
    normalized: list[KnowledgeVectorRecord] = []
    seen: set[int] = set()
    for record in records:
        unit_id = record.unit_id
        if type(unit_id) is not int or unit_id < 1 or unit_id in seen:
            raise KnowledgeVectorStoreError()
        vector = validated_vector(record.vector)
        if len(vector) != dimensions:
            raise KnowledgeVectorStoreError()
        seen.add(unit_id)
        normalized.append(KnowledgeVectorRecord(unit_id=unit_id, vector=vector))
    return normalized


def unit_ids_digest(unit_ids: Sequence[int]) -> str:
    digest = sha256(b"xenix.knowledge.unit-ids.v1\0")
    for unit_id in unit_ids:
        encoded = str(unit_id).encode("ascii")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def manifest_payload(
    *,
    generation_id: int,
    corpus_fingerprint: str,
    profile_fingerprint: str,
    dimensions: int,
    unit_ids: Sequence[int],
) -> dict[str, object]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generation_id": generation_id,
        "corpus_fingerprint": corpus_fingerprint,
        "profile_fingerprint": profile_fingerprint,
        "dimensions": dimensions,
        "unit_count": len(unit_ids),
        "unit_ids_sha256": unit_ids_digest(unit_ids),
    }


def write_manifest(
    path: Path,
    *,
    generation_id: int,
    corpus_fingerprint: str,
    profile_fingerprint: str,
    dimensions: int,
    unit_ids: Sequence[int],
) -> None:
    payload = manifest_payload(
        generation_id=generation_id,
        corpus_fingerprint=corpus_fingerprint,
        profile_fingerprint=profile_fingerprint,
        dimensions=dimensions,
        unit_ids=unit_ids,
    )
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if not encoded or len(encoded) > MAX_MANIFEST_BYTES:
        raise KnowledgeVectorStoreError()
    manifest_path = path / MANIFEST_FILE_NAME
    assert_within(manifest_path, path)
    with manifest_path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def read_manifest(path: Path) -> dict[str, object]:
    manifest_path = path / MANIFEST_FILE_NAME
    assert_within(manifest_path, path)
    if is_link_like(manifest_path) or not manifest_path.is_file():
        raise KnowledgeVectorStoreError()
    with manifest_path.open("rb") as handle:
        encoded = handle.read(MAX_MANIFEST_BYTES + 1)
    if not encoded or len(encoded) > MAX_MANIFEST_BYTES:
        raise KnowledgeVectorStoreError()
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KnowledgeVectorStoreError() from exc
    if not isinstance(payload, dict) or set(payload) != MANIFEST_KEYS:
        raise KnowledgeVectorStoreError()
    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != MANIFEST_SCHEMA_VERSION
        or type(payload["generation_id"]) is not int
        or type(payload["corpus_fingerprint"]) is not str
        or type(payload["profile_fingerprint"]) is not str
        or type(payload["dimensions"]) is not int
        or type(payload["unit_count"]) is not int
        or type(payload["unit_ids_sha256"]) is not str
    ):
        raise KnowledgeVectorStoreError()
    validate_generation_id(payload["generation_id"])
    validated_fingerprint(payload["corpus_fingerprint"])
    validated_fingerprint(payload["profile_fingerprint"])
    validated_positive_int(payload["dimensions"])
    validated_positive_int(payload["unit_count"])
    if not SHA256_PATTERN.fullmatch(payload["unit_ids_sha256"]):
        raise KnowledgeVectorStoreError()
    return payload
