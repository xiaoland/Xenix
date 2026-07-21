from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import zstandard

from ..config import AppPaths
from ..exceptions import ValidationError
from .storage.layout import knowledge_objects_root, knowledge_staging_root


@dataclass(frozen=True)
class StoredKnowledgeSource:
    sha256: str
    path: Path
    size: int


class KnowledgeContentStore:
    """App-owned content-addressed storage for source and canonical bytes."""

    def __init__(self, paths: AppPaths) -> None:
        self._objects = knowledge_objects_root(paths)
        self._staging = knowledge_staging_root(paths)
        self._objects.mkdir(parents=True, exist_ok=True)
        self._staging.mkdir(parents=True, exist_ok=True)

    def snapshot_source(self, source_path: Path) -> StoredKnowledgeSource:
        source = source_path.expanduser().resolve()
        if not source.is_file():
            raise ValidationError("Knowledge source must be an existing local file.")
        staged = self._staging / f"{uuid4().hex}.tmp"
        digest_builder = hashlib.sha256()
        size = 0
        with source.open("rb") as source_stream, staged.open("xb") as target_stream:
            for block in iter(lambda: source_stream.read(1024 * 1024), b""):
                digest_builder.update(block)
                target_stream.write(block)
                size += len(block)
            target_stream.flush()
            os.fsync(target_stream.fileno())
        digest = digest_builder.hexdigest()
        suffix = source.suffix.casefold()
        target = self._object_directory(digest) / f"source{suffix}"
        if target.exists():
            staged.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_publish(staged, target)
        return StoredKnowledgeSource(sha256=digest, path=target, size=size)

    def write_canonical(self, source_sha256: str, payload: bytes) -> Path:
        target = self._object_directory(source_sha256) / "docling-document.json.zst"
        if target.exists():
            return target
        compressed = zstandard.ZstdCompressor(level=7).compress(payload)
        self._publish_bytes(compressed, target)
        return target

    def _object_directory(self, digest: str) -> Path:
        return self._objects / digest[:2] / digest[2:4] / digest

    def _publish_bytes(self, payload: bytes, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        staged = self._staging / f"{uuid4().hex}.tmp"
        staged.write_bytes(payload)
        self._atomic_publish(staged, target)

    @staticmethod
    def _atomic_publish(staged: Path, target: Path) -> None:
        try:
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)
